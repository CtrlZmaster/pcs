import sys
import json
import logging

from pcs import settings, utils
from pcs.cli.common.env_cli import Env
from pcs.cli.common.lib_wrapper import Library
from pcs.common.reports import (
    ReportItem,
    ReportItemDto,
    ReportItemList,
    ReportProcessor,
)
from pcs.lib.errors import LibraryError


SUPPORTED_COMMANDS = {
    "cluster.setup",
    "cluster.add_nodes",
    "cluster.remove_nodes",
    "status.full_cluster_status_plaintext",
}


def _exit(status, status_msg=None, report_list=None, data=None):
    json.dump(
        dict(
            status=status,
            status_msg=status_msg,
            report_list=report_list or [],
            data=data,
        ),
        sys.stdout,
    )
    sys.exit(0)


def get_cli_env(options):
    env = Env()
    env.user, env.groups = utils.get_cib_user_groups()
    env.known_hosts_getter = utils.read_known_hosts_file
    # Debug messages always go to the processor. The parameter only affects if
    # they will be printed to stdout. We are not printing the messages. Instead
    # we get all the messages the processor got. So the value of the parameter
    # does not matter.
    env.report_processor = LibraryReportProcessor()
    env.request_timeout = (
        options.get("request_timeout") or settings.default_request_timeout
    )
    return env


class LibraryReportProcessor(ReportProcessor):
    processed_items: ReportItemList = []

    def _do_report(self, report_item: ReportItem) -> None:
        self.processed_items.append(report_item)


def export_reports(report_list):
    return [report_item_to_dict(report) for report in report_list]


def report_item_to_dict(report_item: ReportItem):
    dto_obj: ReportItemDto = report_item.to_dto()
    return dict(
        severity=dto_obj.severity.level,
        code=dto_obj.message.code,
        info=dto_obj.message.payload,
        forceable=dto_obj.severity.force_code,
        report_text=dto_obj.message.message,
    )


def main():
    # pylint: disable=broad-except
    argv = sys.argv[1:]
    if argv:
        _exit("input_error", status_msg="No arguments allowed")

    utils.subprocess_setup()
    logging.basicConfig()

    try:
        input_data = json.load(sys.stdin)
        cli_env = get_cli_env(input_data.get("options", {}))
        lib = Library(cli_env, utils.get_middleware_factory())
        cmd = input_data["cmd"]
        if cmd not in SUPPORTED_COMMANDS:
            _exit("unknown_cmd", status_msg=f"Unknown command '{cmd}'")
        for sub_cmd in cmd.split("."):
            lib = getattr(lib, sub_cmd)
        output_data = lib(**input_data["cmd_data"])
        _exit(
            "success",
            report_list=export_reports(
                cli_env.report_processor.processed_items
            ),
            data=output_data,
        )
    except LibraryError as e:
        _exit(
            "error",
            report_list=export_reports(
                cli_env.report_processor.processed_items + list(e.args)
            ),
        )
    except json.JSONDecodeError as e:
        _exit("input_error", status_msg=f"Unable to parse input data: {e.msg}")
    except KeyError as e:
        _exit("input_error", status_msg=f"Missing key {e}")
    except Exception as e:
        # TODO: maybe add traceback?
        _exit("exception", status_msg=str(e))
