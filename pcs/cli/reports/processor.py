from typing import Iterable

from pcs.cli.common.tools import print_to_stderr
from pcs.common.reports import (
    ReportItem,
    ReportItemDto,
    ReportItemSeverity,
    ReportProcessor,
)

from .messages import report_item_msg_from_dto
from .output import (
    deprecation_warning,
    error,
    prepare_force_text,
    warn,
)


def print_report_dto(
    report_dto: ReportItemDto,
    ignore_severities: Iterable[ReportItemSeverity] = (),
    debug: bool = False,
) -> None:
    msg = report_item_msg_from_dto(report_dto.message).message
    if report_dto.context:
        msg = f"{report_dto.context.node}: {msg}"
    severity = report_dto.severity.level

    if severity in list(ignore_severities):
        # DEBUG overrides ignoring severities for debug reports
        if msg and debug and severity == ReportItemSeverity.DEBUG:
            print_to_stderr(msg)
        return

    if severity == ReportItemSeverity.ERROR:
        error(
            "{msg}{force}".format(
                msg=msg,
                force=prepare_force_text(
                    ReportItemSeverity.from_dto(report_dto.severity)
                ),
            )
        )
    elif severity == ReportItemSeverity.WARNING:
        warn(msg)
    elif severity == ReportItemSeverity.DEPRECATION:
        deprecation_warning(msg)
    elif msg and (debug or severity != ReportItemSeverity.DEBUG):
        print_to_stderr(msg)


class ReportProcessorToConsole(ReportProcessor):
    def __init__(self, debug: bool = False) -> None:
        super().__init__()
        self._ignore_severities: Iterable[ReportItemSeverity] = []
        self.debug = debug

    def _do_report(self, report_item: ReportItem) -> None:
        report_dto = report_item.to_dto()
        print_report_dto(report_dto, self._ignore_severities, self.debug)

    def suppress_reports_of_severity(
        self, severity_list: Iterable[ReportItemSeverity]
    ) -> None:
        self._ignore_severities = list(severity_list)
