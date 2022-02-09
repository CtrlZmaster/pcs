from collections import defaultdict
from dataclasses import replace as dc_replace
from typing import Dict, Iterable, List, Optional, Set

from lxml import etree

from pcs import settings
from pcs.common import reports
from pcs.lib import validate
from pcs.lib.external import CommandRunner

from . import const
from .error import (
    ResourceAgentError,
    resource_agent_error_to_report_item,
    UnableToGetAgentMetadata,
)
from .name import name_to_void_metadata
from .ocf_transform import ocf_version_to_ocf_unified
from .pcs_transform import get_additional_trace_parameters, ocf_unified_to_pcs
from .types import (
    ResourceAgentMetadata,
    ResourceAgentName,
    ResourceAgentParameter,
)
from .xml import load_fake_agent_metadata, load_metadata, parse_metadata


class ResourceAgentFacade:
    """
    Provides metadata of and validators for a resource / stonith agent
    """

    def __init__(
        self,
        metadata: ResourceAgentMetadata,
        additional_parameters: Optional[
            Iterable[ResourceAgentParameter]
        ] = None,
    ) -> None:
        """
        metadata -- parsed OCF metadata in a universal format (not version specific)
        additional_parameters -- resource parameters defined outside an agent
        """
        self._raw_metadata = metadata
        self._additional_parameters = additional_parameters
        self._pcs_metadata_cache: Optional[ResourceAgentMetadata] = None

    @property
    def metadata(self) -> ResourceAgentMetadata:
        """
        Return cleaned agent metadata
        """
        if self._pcs_metadata_cache is None:
            self._pcs_metadata_cache = self._get_metadata()
        return self._pcs_metadata_cache

    def _get_metadata(self) -> ResourceAgentMetadata:
        pcs_metadata = ocf_unified_to_pcs(self._raw_metadata)
        if self._additional_parameters:
            pcs_metadata = dc_replace(
                pcs_metadata,
                parameters=(
                    pcs_metadata.parameters + list(self._additional_parameters)
                ),
            )
        return pcs_metadata

    # Facade provides just a basic validation checking that required parameters
    # are set and all set parameters are known to an agent. Missing checks are:
    # 1. values checks - if a param is an integer, then "abc" is not valid
    # 2. errors should be emitted when a deprecated parameter and a
    #    parameter obsoleting it are set at the same time
    # 3. possibly some other checks
    # All of these have been missing in pcs since ever (ad 1. agents have not
    # provided enough info for us to do such validations, ad 3. there were no
    # deprecated parameters before). The checks should be implemented in agents
    # themselves, so we're not adding them now either.

    def get_validators_allowed_parameters(
        self, force: bool = False
    ) -> List[validate.ValidatorInterface]:
        """
        Return validators checking for specified parameters names

        force -- if True, validators produce a warning instead of an error
        """
        return [
            validate.NamesIn(
                {param.name for param in self.metadata.parameters},
                self._validator_option_type,
                severity=reports.item.get_severity(reports.codes.FORCE, force),
            )
        ]

    def get_validators_deprecated_parameters(
        self,
    ) -> List[validate.ValidatorInterface]:
        """
        Return validators looking for deprecated parameters
        """
        # Setting deprecated parameters always emit a warning - we want to allow
        # using them not to break backward compatibility.
        return [
            validate.DeprecatedOption(
                [param.name],
                param.deprecated_by,
                self._validator_option_type,
                severity=reports.ReportItemSeverity.warning(),
            )
            for param in self.metadata.parameters
            if param.deprecated
        ]

    def get_validators_required_parameters(
        self,
        force: bool = False,
        only_parameters: Optional[Iterable[str]] = None,
    ) -> List[validate.ValidatorInterface]:
        """
        Return validators checking if required parameters were specified

        force -- if True, validators produce a warning instead of an error
        only_parameters -- if set, only specified parameters are checked
        """
        validators: List[validate.ValidatorInterface] = []
        severity = reports.item.get_severity(reports.codes.FORCE, force)
        only_parameters = only_parameters or set()

        required_not_obsoleting: Set[str] = set()
        all_params_deprecated_by = self._get_all_params_deprecated_by()
        for param in self.metadata.parameters:
            if not param.required or param.deprecated:
                continue
            deprecated_by_param = all_params_deprecated_by[param.name]
            if only_parameters and not (
                {param.name} | deprecated_by_param
            ).intersection(only_parameters):
                continue
            if deprecated_by_param:
                validators.append(
                    validate.IsRequiredSome(
                        {param.name} | deprecated_by_param,
                        self._validator_option_type,
                        deprecated_option_name_list=deprecated_by_param,
                        severity=severity,
                    )
                )
            else:
                required_not_obsoleting.add(param.name)

        if required_not_obsoleting:
            validators.append(
                validate.IsRequiredAll(
                    required_not_obsoleting,
                    self._validator_option_type,
                    severity,
                )
            )

        return validators

    @property
    def _validator_option_type(self):
        return "stonith" if self.metadata.name.is_stonith else "resource"

    def _get_all_params_deprecated_by(self) -> Dict[str, Set[str]]:
        new_olds_map: Dict[str, Set[str]] = defaultdict(set)
        for param in self.metadata.parameters:
            for new_name in param.deprecated_by:
                new_olds_map[new_name].add(param.name)

        result: Dict[str, Set[str]] = defaultdict(set)
        for param in self.metadata.parameters:
            discovered = new_olds_map[param.name]
            while discovered:
                result[param.name] |= discovered
                new_discovered = set()
                for name in discovered:
                    new_discovered |= new_olds_map[name]
                discovered = new_discovered - result[param.name]
        return result


class ResourceAgentFacadeFactory:
    """
    Creates ResourceAgentFacade instances
    """

    def __init__(
        self, runner: CommandRunner, report_processor: reports.ReportProcessor
    ) -> None:
        self._runner = runner
        self._report_processor = report_processor
        self._fenced_metadata = None

    def facade_from_parsed_name(
        self, name: ResourceAgentName, report_warnings=True
    ) -> ResourceAgentFacade:
        """
        Create ResourceAgentFacade based on specified agent name

        name -- agent name to get a facade for
        """
        dom_metadata = load_metadata(self._runner, name)
        metadata, raw_ocf_version = parse_metadata(name, dom_metadata)
        if report_warnings:
            if raw_ocf_version not in const.SUPPORTED_OCF_VERSIONS:
                self._report_processor.report(
                    reports.ReportItem.warning(
                        reports.messages.AgentImplementsUnsupportedOcfVersionAssumedVersion(
                            name.full_name,
                            raw_ocf_version,
                            sorted(const.SUPPORTED_OCF_VERSIONS),
                            const.OCF_1_0,
                        )
                    )
                )
            if raw_ocf_version != const.OCF_1_1:
                try:
                    etree.RelaxNG(
                        file=settings.path.ocf_1_0_schema
                    ).assertValid(dom_metadata)
                except etree.DocumentInvalid as e:
                    self._report_processor.report(
                        resource_agent_error_to_report_item(
                            UnableToGetAgentMetadata(name.full_name, str(e)),
                            severity=reports.ReportItemSeverity.warning(),
                            is_stonith=name.is_stonith,
                        )
                    )
        return self._facade_from_metadata(ocf_version_to_ocf_unified(metadata))

    def void_facade_from_parsed_name(
        self, name: ResourceAgentName
    ) -> ResourceAgentFacade:
        """
        Create ResourceAgentFacade for a non-existent agent

        name -- name of a non-existent agent to put into the facade
        """
        return self._facade_from_metadata(name_to_void_metadata(name))

    def _facade_from_metadata(
        self, metadata: ResourceAgentMetadata
    ) -> ResourceAgentFacade:
        additional_parameters = []
        if metadata.name.is_stonith:
            additional_parameters += self._get_fenced_parameters()
        if metadata.name.standard == "ocf" and metadata.name.provider in (
            "heartbeat",
            "pacemaker",
        ):
            additional_parameters += get_additional_trace_parameters(
                metadata.parameters
            )
        return ResourceAgentFacade(metadata, additional_parameters)

    def _get_fenced_parameters(self):
        if self._fenced_metadata is None:
            agent_name = ResourceAgentName(
                const.FAKE_AGENT_STANDARD, None, const.PACEMAKER_FENCED
            )
            try:
                metadata, _ = parse_metadata(
                    agent_name,
                    load_fake_agent_metadata(self._runner, agent_name.type),
                )
                self._fenced_metadata = ocf_unified_to_pcs(
                    ocf_version_to_ocf_unified(metadata)
                )
            except ResourceAgentError as e:
                # If pcs is unable to load fenced metadata, cache an empty
                # metadata in order to prevent further futile attempts to load
                # them.
                # Since we are recovering from the failure, we report it as a
                # warning.
                self._report_processor.report(
                    resource_agent_error_to_report_item(
                        e, severity=reports.ReportItemSeverity.warning()
                    )
                )
                self._fenced_metadata = name_to_void_metadata(agent_name)
        return self._fenced_metadata.parameters