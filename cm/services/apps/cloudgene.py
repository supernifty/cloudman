import os
import tarfile
# from ansible.runner import Runner
# from ansible.inventory import Inventory

from cm.util import misc
import cm.util.paths as paths
from cm.services import ServiceRole
from cm.services import ServiceDependency
from cm.services import service_states
from cm.services.apps import ApplicationService

import logging
log = logging.getLogger('cloudman')


class CloudgeneService(ApplicationService):
    def __init__(self, app):
        super(CloudgeneService, self).__init__(app)
        self.svc_roles = [ServiceRole.CLOUDGENE]
        self.name = ServiceRole.to_string(ServiceRole.CLOUDGENE)
        self.dependencies = [ServiceDependency(self, ServiceRole.CLOUDERA_MANAGER)]
        self.port = 8085
        self.cg_url = "http://cloudgene.uibk.ac.at/downloads/cloudgene-cloudman.tar.gz"
        self.cg_base_dir = '/mnt/galaxy/cloudgene/'
        self.cg_home = os.path.join(self.cg_base_dir, 'cloudgene-cloudman')

    def start(self):
        """
        Start Cloudgene service.
        """
        log.debug("Starting Cloudgene service")
        self.state = service_states.STARTING
        self._configure()
        self._start_server()

    def remove(self, synchronous=False):
        """
        Stop the Cloudgene service.
        """
        log.info("Stopping Cloudgene service")
        super(CloudgeneService, self).remove(synchronous)
        self.state = service_states.SHUTTING_DOWN
        if misc.run('{0} - cloudgene -c "cd {1}; sh stop.sh"'.format(paths.P_SU,
                    self.cg_base_dir)):
            self.state = service_states.SHUT_DOWN

    def __run_as_clougene_user(self, cmd):
        """
        Convenience method that wrapps `cmd` to be run as `cloudgene` system
        user.
        """
        return misc.run('{0} - cloudgene -c "{1}"'.format(paths.P_SU, cmd))

    def _configure(self):
        """
        Download the Cloudgene source and extract the archive
        """
        log.debug("Configuring Cloudgene")
        if not os.path.exists(self.cg_base_dir):
            os.mkdir(self.cg_base_dir)
        cg_source_file = 'cg.tar.gz'
        cg_source = os.path.join(self.cg_base_dir, cg_source_file)
        # Download Cloudgene source
        log.debug("Downloading Clougene...")
        misc.run("wget --output-document='{0}' {1}".format(cg_source, self.cg_url))
        # Extract the source
        with tarfile.open(cg_source, 'r:gz') as tar:
            tar.extractall(self.cg_base_dir)
        misc.run("cd {0}; chmod +x start.sh state.sh stop.sh".format(self.cg_home))
        misc.run("chown -R -c cloudgene {0}".format(self.cg_base_dir))
        # Create Cloudgene home folder in HDFS
        if not misc.run("sudo -u hdfs hadoop fs -test -e /user/cloudgene", quiet=True):
            misc.run("sudo -u hdfs hadoop fs -mkdir /user/cloudgene")
        misc.run("sudo -u hdfs hadoop fs -chown cloudgene /user/cloudgene")

    def _start_server(self):
        """
        Start the Cloudgene server. It will be started on port specified in
        ``port`` class field.
        """
        log.debug("Starting Cloudgene server")
        if self.__run_as_clougene_user("cd {0}; sh start.sh".format(self.cg_home)):
            self.state = service_states.RUNNING

    def status(self):
        """
        Check and update the status of the service.
        """
        if self.state == service_states.UNSTARTED or \
           self.state == service_states.STARTING or \
           self.state == service_states.SHUTTING_DOWN or \
           self.state == service_states.SHUT_DOWN or \
           self.state == service_states.WAITING_FOR_USER_ACTION:
            pass
        elif 'NOT running' in misc.getoutput("cd {0}; sh state.sh".format(
             self.cg_home), quiet=True):
            log.error("Cloudgene server not running!")
            self.state == service_states.ERROR
        else:
            self.state = service_states.RUNNING
