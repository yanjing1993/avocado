"""
Implements the base avocado runner application.
"""
import imp
import logging
import os
import time
from argparse import ArgumentParser

from avocado import sysinfo
from avocado.core import data_dir
from avocado.core import output

log = logging.getLogger("avocado.app")


def run_tests(args):
    """
    Find test modules in tests dir and run them.

    :param args: Command line arguments.
    """
    test_start_time = time.strftime('%Y-%m-%d-%H.%M.%S')
    logdir = args.logdir or data_dir.get_logs_dir()
    debugbase = 'run-%s' % test_start_time
    debugdir = os.path.join(logdir, debugbase)
    latestdir = os.path.join(logdir, "latest")
    if not os.path.isdir(debugdir):
        os.makedirs(debugdir)
    try:
        os.unlink(latestdir)
    except OSError:
        pass
    os.symlink(debugbase, latestdir)

    debuglog = os.path.join(debugdir, "debug.log")
    loglevel = args.log_level or logging.INFO
    output_manager = output.OutputManager()

    job_file_handler = output_manager.create_file_handler(debuglog, loglevel)

    urls = args.url.split()
    total_tests = len(urls)
    test_dir = data_dir.get_test_dir()
    output_manager.log_header("DEBUG LOG: %s" % debuglog)
    output_manager.log_header("TOTAL TESTS: %s" % total_tests)
    output_mapping = {'PASS': output_manager.log_pass,
                      'FAIL': output_manager.log_fail,
                      'TEST_NA': output_manager.log_skip,
                      'WARN': output_manager.log_warn}

    test_index = 1

    for url in urls:
        test_module_dir = os.path.join(test_dir, url)
        f, p, d = imp.find_module(url, [test_module_dir])
        test_module = imp.load_module(url, f, p, d)
        f.close()
        test_class = getattr(test_module, url)
        test_instance = test_class(name=url, base_logdir=debugdir)
        sysinfo_logger = sysinfo.SysInfo(basedir=test_instance.sysinfodir)
        test_file_handler = output_manager.create_file_handler(
                                                test_instance.logfile, loglevel)
        test_instance.setup()
        sysinfo_logger.start_job_hook()
        test_instance.run()
        test_instance.cleanup()
        output_func = output_mapping[test_instance.status]
        label = "(%s/%s) %s:" % (test_index, total_tests,
                                 test_instance.tagged_name)
        output_func(label, test_instance.time_elapsed)
        test_index += 1
        output_manager.remove_file_handler(test_file_handler)

    output_manager.remove_file_handler(job_file_handler)


class AvocadoRunnerApp(object):

    """
    Basic avocado runner application.
    """

    def __init__(self):
        self.arg_parser = ArgumentParser(description='Avocado Test Runner')
        self.arg_parser.add_argument('-v', '--verbose', action='store_true',
                                     help='print extra debug messages',
                                     dest='verbose')
        self.arg_parser.add_argument('--logdir', action='store',
                                     help='Alternate logs directory',
                                     dest='logdir', default='')
        self.arg_parser.add_argument('--loglevel', action='store',
                                     help='Debug Level',
                                     dest='log_level', default='')

        subparsers = self.arg_parser.add_subparsers(title='subcommands',
                                                    description='valid subcommands',
                                                    help='subcommand help')

        prun = subparsers.add_parser('run', help='Run a single test module')
        prun.add_argument('url', type=str,
                          help='Test module names (space separated)',
                          nargs='?', default='')
        prun.set_defaults(func=run_tests)

        psysinfo = subparsers.add_parser('sysinfo',
                                         help='Collect system information')
        psysinfo.add_argument('sysinfodir', type=str,
                              help='Dir where to dump sysinfo',
                              nargs='?', default='')
        psysinfo.set_defaults(func=sysinfo.collect_sysinfo)

        self.args = self.arg_parser.parse_args()

    def run(self):
        self.args.func(self.args)
