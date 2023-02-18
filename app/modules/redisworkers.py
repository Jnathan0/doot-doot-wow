import subprocess
# import to look at rq workers
from rq.worker import Worker
from modules import config


class RedisWorker():
    def __init__(self):
        # self.enable_rq_scheduler()
        self.create_rq_workers()

    def enable_rq_scheduler(self):
            """
            enables the rq scheduler script
            """
            subprocess.Popen(['/bin/bash', '/usr/local/bin/rqscheduler'])

    def create_rq_workers(self):
        """
        Checks to see if rq workers are active with names in "workers".
        If they are not, they are started. 
        """
        workers = {
                    'plays': 'rq:worker:plays', 
                    'generic_worker': 'rq:worker:generic_worker', 
                    'metadata': 'rq:worker:metadata'
                }
        for worker_name, worker_key in workers.items():
            if Worker.find_by_key(worker_key, connection=config.redis_connection) is None:
                print(f"Worker [{worker_name}] not found, creating...")
                if worker_name == 'metadata' or worker_name == 'generic_worker':
                    subprocess.Popen(['rqworker', '--with-scheduler', f'{worker_name}', '--name', f'{worker_name}'])
                else:
                    subprocess.Popen(['rqworker', f'{worker_name}', '--name', f'{worker_name}'])
            else:
                print(f"Worker [{worker_name}] found, skipping")
