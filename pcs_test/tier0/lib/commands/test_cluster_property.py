import os
from unittest import TestCase, mock

from pcs import settings
from pcs.common import reports
from pcs.common.pacemaker.cluster_property import ClusterPropertyMetadataDto
from pcs.common.pacemaker.nvset import (
    CibNvpairDto,
    CibNvsetDto,
    ListCibNvsetDto,
)
from pcs.common.resource_agent.dto import ResourceAgentParameterDto
from pcs.lib.commands import cluster_property

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.misc import get_test_resource as rc

ALLOWED_PROPERTIES = [
    "batch-limit",
    "cluster-delay",
    "cluster-ipc-limit",
    "cluster-recheck-interval",
    "concurrent-fencing",
    "dc-deadtime",
    "election-timeout",
    "enable-acl",
    "enable-startup-probes",
    "fence-reaction",
    "join-finalization-timeout",
    "join-integration-timeout",
    "load-threshold",
    "maintenance-mode",
    "migration-limit",
    "no-quorum-policy",
    "node-action-limit",
    "node-health-base",
    "node-health-green",
    "node-health-red",
    "node-health-strategy",
    "node-health-yellow",
    "node-pending-timeout",
    "pe-error-series-max",
    "pe-input-series-max",
    "pe-warn-series-max",
    "placement-strategy",
    "priority-fencing-delay",
    "remove-after-stop",
    "shutdown-escalation",
    "shutdown-lock",
    "shutdown-lock-limit",
    "start-failure-is-fatal",
    "startup-fencing",
    "stonith-action",
    "stonith-enabled",
    "stonith-max-attempts",
    "stonith-timeout",
    "stonith-watchdog-timeout",
    "stop-all-resources",
    "stop-orphan-actions",
    "stop-orphan-resources",
    "symmetric-cluster",
    "transition-delay",
]

READONLY_PROPERTIES = [
    "cluster-infrastructure",
    "cluster-name",
    "dc-version",
    "have-watchdog",
    "last-lrm-refresh",
]


def fixture_property_set(set_id, nvpairs, score=None):
    score_attr = ""
    if score:
        score_attr = f'score="{score}"'
    return (
        f'<cluster_property_set id="{set_id}" {score_attr}>'
        + "".join(
            [
                f'<nvpair id="{set_id}-{name}" name="{name}" value="{value}"/>'
                for name, value in nvpairs.items()
                if value
            ]
        )
        + "</cluster_property_set>"
    )


def fixture_crm_config_properties(set_list, score_list=None):
    return (
        "<crm_config>"
        + "".join(
            [
                fixture_property_set(
                    set_tuple[0],
                    set_tuple[1],
                    score=None if not score_list else score_list[idx],
                )
                for idx, set_tuple in enumerate(set_list)
            ]
        )
        + "</crm_config>"
    )


class CrmAttributeLoadMetadataMixin:
    def load_fake_agent_metadata(self):
        self.config.runner.pcmk.is_crm_attribute_list_options_supported(
            is_supported=True
        )
        self.config.runner.pcmk.load_crm_attribute_metadata()


class StonithWatchdogTimeoutMixin:
    sbd_enabled = None

    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.runner.cib.load(
            crm_config=fixture_crm_config_properties(
                [("cib-bootstrap-options", {"stonith-watchdog-timeout": "10"})]
            )
        )
        self.load_fake_agent_metadata()
        self.config.services.is_enabled("sbd", return_value=self.sbd_enabled)

    def _set_success(self, options_dict):
        self.config.env.push_cib(
            crm_config=fixture_crm_config_properties(
                [("cib-bootstrap-options", options_dict)]
            )
        )
        cluster_property.set_properties(
            self.env_assist.get_env(), options_dict, []
        )
        self.env_assist.assert_reports([])

    def _set_invalid_value(self, forced=False):
        self.config.remove("services.is_enabled")
        self.env_assist.assert_raise_library_error(
            lambda: cluster_property.set_properties(
                self.env_assist.get_env(),
                {"stonith-watchdog-timeout": "15x"},
                [] if not forced else [reports.codes.FORCE],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="stonith-watchdog-timeout",
                    option_value="15x",
                    allowed_values="time interval (e.g. 1, 2s, 3m, 4h, ...)",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ]
        )

    def test_set_invalid_value(self):
        self._set_invalid_value(forced=False)

    def test_set_invalid_value_forced(self):
        self._set_invalid_value(forced=True)


class SetStonithWatchdogTimeoutSBDIsDisabledMixin(StonithWatchdogTimeoutMixin):
    sbd_enabled = False

    def test_set_empty(self):
        self._set_success({"stonith-watchdog-timeout": ""})

    def test_set_zero(self):
        self._set_success({"stonith-watchdog-timeout": "0"})

    def test_set_zero_time_suffix(self):
        self._set_success({"stonith-watchdog-timeout": "0s"})

    def test_set_not_zero_or_empty(self):
        self.env_assist.assert_raise_library_error(
            lambda: cluster_property.set_properties(
                self.env_assist.get_env(),
                {"stonith-watchdog-timeout": "20"},
                [],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.STONITH_WATCHDOG_TIMEOUT_CANNOT_BE_SET,
                    reason="sbd_not_set_up",
                ),
            ]
        )

    def test_set_not_zero_or_empty_forced(self):
        self.env_assist.assert_raise_library_error(
            lambda: cluster_property.set_properties(
                self.env_assist.get_env(),
                {"stonith-watchdog-timeout": "20"},
                [reports.codes.FORCE],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.STONITH_WATCHDOG_TIMEOUT_CANNOT_BE_SET,
                    reason="sbd_not_set_up",
                ),
            ]
        )


@mock.patch.object(
    settings,
    "pacemaker_api_result_schema",
    rc("pcmk_api_rng/api-result.rng"),
)
class TestSetStonithWatchdogTimeoutSBDIsDisabledCrmAttributeMetadata(
    CrmAttributeLoadMetadataMixin,
    SetStonithWatchdogTimeoutSBDIsDisabledMixin,
    TestCase,
):
    pass


class SetStonithWatchdogTimeoutSBDIsEnabledWatchdogOnlyMixin(
    StonithWatchdogTimeoutMixin
):
    sbd_enabled = True

    def test_set_empty(self):
        self.env_assist.assert_raise_library_error(
            lambda: cluster_property.set_properties(
                self.env_assist.get_env(), {"stonith-watchdog-timeout": ""}, []
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.STONITH_WATCHDOG_TIMEOUT_CANNOT_BE_UNSET,
                    force_code=reports.codes.FORCE,
                    reason="sbd_set_up_without_devices",
                )
            ]
        )

    def test_set_empty_forced(self):
        self.config.env.push_cib(
            crm_config=fixture_crm_config_properties(
                [("cib-bootstrap-options", {})]
            )
        )
        cluster_property.set_properties(
            self.env_assist.get_env(),
            {"stonith-watchdog-timeout": ""},
            [reports.codes.FORCE],
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.STONITH_WATCHDOG_TIMEOUT_CANNOT_BE_UNSET,
                    reason="sbd_set_up_without_devices",
                )
            ]
        )

    def test_set_zero(self):
        self.env_assist.assert_raise_library_error(
            lambda: cluster_property.set_properties(
                self.env_assist.get_env(),
                {"stonith-watchdog-timeout": "0"},
                [],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.STONITH_WATCHDOG_TIMEOUT_CANNOT_BE_UNSET,
                    force_code=reports.codes.FORCE,
                    reason="sbd_set_up_without_devices",
                )
            ]
        )

    def test_set_zero_forced(self):
        self.config.env.push_cib(
            crm_config=fixture_crm_config_properties(
                [("cib-bootstrap-options", {"stonith-watchdog-timeout": "0s"})]
            )
        )
        cluster_property.set_properties(
            self.env_assist.get_env(),
            {"stonith-watchdog-timeout": "0s"},
            [reports.codes.FORCE],
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.STONITH_WATCHDOG_TIMEOUT_CANNOT_BE_UNSET,
                    reason="sbd_set_up_without_devices",
                )
            ]
        )

    def test_equal_to_timeout(self):
        self.env_assist.assert_raise_library_error(
            lambda: cluster_property.set_properties(
                self.env_assist.get_env(),
                {"stonith-watchdog-timeout": "10"},
                [],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.STONITH_WATCHDOG_TIMEOUT_TOO_SMALL,
                    force_code=reports.codes.FORCE,
                    cluster_sbd_watchdog_timeout=10,
                    entered_watchdog_timeout="10",
                )
            ]
        )

    def test_too_small(self):
        self.env_assist.assert_raise_library_error(
            lambda: cluster_property.set_properties(
                self.env_assist.get_env(),
                {"stonith-watchdog-timeout": "9s"},
                [],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.STONITH_WATCHDOG_TIMEOUT_TOO_SMALL,
                    force_code=reports.codes.FORCE,
                    cluster_sbd_watchdog_timeout=10,
                    entered_watchdog_timeout="9s",
                )
            ]
        )

    def test_too_small_forced(self):
        self.config.env.push_cib(
            crm_config=fixture_crm_config_properties(
                [("cib-bootstrap-options", {"stonith-watchdog-timeout": "9s"})]
            )
        )
        cluster_property.set_properties(
            self.env_assist.get_env(),
            {"stonith-watchdog-timeout": "9s"},
            [reports.codes.FORCE],
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.STONITH_WATCHDOG_TIMEOUT_TOO_SMALL,
                    cluster_sbd_watchdog_timeout=10,
                    entered_watchdog_timeout="9s",
                )
            ]
        )

    def test_more_than_timeout(self):
        self._set_success({"stonith-watchdog-timeout": "11s"})


@mock.patch("pcs.lib.sbd._get_local_sbd_watchdog_timeout", lambda: 10)
@mock.patch("pcs.lib.sbd.get_local_sbd_device_list", list)
class TestSetStonithWatchdogTimeoutSBDIsEnabledWatchdogOnlyMixinCrmAttributeMetadata(
    CrmAttributeLoadMetadataMixin,
    SetStonithWatchdogTimeoutSBDIsEnabledWatchdogOnlyMixin,
    TestCase,
):
    pass


class SetStonithWatchdogTimeoutSBDIsEnabledSharedDevicesMixin(
    StonithWatchdogTimeoutMixin
):
    sbd_enabled = True

    def test_set_empty(self):
        self._set_success({"stonith-watchdog-timeout": ""})

    def test_set_to_zero(self):
        self._set_success({"stonith-watchdog-timeout": "0"})

    def test_set_to_zero_time_suffix(self):
        self._set_success({"stonith-watchdog-timeout": "0min"})

    def test_set_not_zero_or_empty(self):
        self.env_assist.assert_raise_library_error(
            lambda: cluster_property.set_properties(
                self.env_assist.get_env(),
                {"stonith-watchdog-timeout": "20"},
                [],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.STONITH_WATCHDOG_TIMEOUT_CANNOT_BE_SET,
                    force_code=reports.codes.FORCE,
                    reason="sbd_set_up_with_devices",
                )
            ]
        )

    def test_set_not_zero_or_empty_forced(self):
        self.config.env.push_cib(
            crm_config=fixture_crm_config_properties(
                [("cib-bootstrap-options", {"stonith-watchdog-timeout": "20"})]
            )
        )
        cluster_property.set_properties(
            self.env_assist.get_env(),
            {"stonith-watchdog-timeout": "20"},
            [reports.codes.FORCE],
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.STONITH_WATCHDOG_TIMEOUT_CANNOT_BE_SET,
                    reason="sbd_set_up_with_devices",
                )
            ]
        )


@mock.patch.object(
    settings,
    "pacemaker_api_result_schema",
    rc("pcmk_api_rng/api-result.rng"),
)
@mock.patch("pcs.lib.sbd.get_local_sbd_device_list", lambda: ["dev1", "dev2"])
class TestSetStonithWatchdogTimeoutSBDIsEnabledSharedDevicesCrmAttributeMetadata(
    CrmAttributeLoadMetadataMixin,
    SetStonithWatchdogTimeoutSBDIsEnabledSharedDevicesMixin,
    TestCase,
):
    pass


class CrmAttributeMetadataErrorMixin:
    _load_cib_when_metadata_error = None

    def metadata_error_command(self):
        raise NotImplementedError

    def _metadata_error(
        self,
        agent="cluster-options",
        stdout=None,
        stderr="",
        reason=None,
        returncode=2,
        unsupported_version=False,
    ):
        if self._load_cib_when_metadata_error:
            self.config.runner.cib.load()
        self.config.runner.pcmk.is_crm_attribute_list_options_supported(
            is_supported=True
        )
        self.config.runner.pcmk.load_crm_attribute_metadata(
            agent_name=agent,
            stdout=stdout,
            stderr=stderr,
            returncode=returncode,
        )
        self.env_assist.assert_raise_library_error(self.metadata_error_command)
        if unsupported_version:
            report = fixture.error(
                reports.codes.AGENT_IMPLEMENTS_UNSUPPORTED_OCF_VERSION,
                agent=f"__pcmk_internal:{agent}",
                ocf_version="5.2",
                supported_versions=["1.0", "1.1"],
            )
        else:
            report = fixture.error(
                reports.codes.UNABLE_TO_GET_AGENT_METADATA,
                agent=agent,
                reason="error" if reason is None else reason,
            )
        self.env_assist.assert_reports([report])

    def test_metadata_error_returncode(self):
        stdout = """
            <pacemaker-result api-version="2.38" request="crm_attribute">
                <status code="2" message="ERROR" />
            </pacemaker-result>
        """
        self._metadata_error(stdout=stdout, reason="ERROR")

    def test_metadata_error_xml_syntax_error(self):
        stdout = "not an xml"
        stderr = "syntax error"
        self._metadata_error(
            stdout=stdout, stderr=stderr, reason=f"{stderr}\n{stdout}"
        )

    def test_metadata_error_invalid_schema(self):
        stdout = "<xml/>"
        stderr = "invalid schema"
        self._metadata_error(
            stdout=stdout, stderr=stderr, reason=f"{stderr}\n{stdout}"
        )

    def test_metadata_error_invalid_version(self):
        stdout = """
            <pacemaker-result api-version="2.38" request="crm_attribute">
                <resource-agent name="cluster-options">
                    <version>5.2</version>
                    <parameters>
                        <parameter name="parameter-name" advanced="0"
                                generated="0">
                            <longdesc lang="en">longdesc</longdesc>
                            <shortdesc lang="en">shortdesc</shortdesc>
                            <content type="string"/>
                        </parameter>
                    </parameters>
                </resource-agent>
                <status code="0" message="OK" />
            </pacemaker-result>
        """
        self._metadata_error(
            stdout=stdout, returncode=0, unsupported_version=True
        )

    def test_facade_crm_attribute_metadata_not_supported(self):
        if self._load_cib_when_metadata_error:
            self.config.runner.cib.load()
        self.config.runner.pcmk.is_crm_attribute_list_options_supported(
            is_supported=False
        )
        self.env_assist.assert_raise_library_error(self.metadata_error_command)
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.CLUSTER_OPTIONS_METADATA_NOT_SUPPORTED
                )
            ]
        )


class TestPropertySetMixin:
    _load_cib_when_metadata_error = True

    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def command(self, prop_dict, force_codes=None):
        cluster_property.set_properties(
            self.env_assist.get_env(),
            prop_dict,
            [] if force_codes is None else force_codes,
        )

    def metadata_error_command(self):
        return self.command({}, [])

    def test_no_properties_specified(self):
        self.config.runner.cib.load()
        self.load_fake_agent_metadata()
        self.env_assist.assert_raise_library_error(lambda: self.command({}))
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.ADD_REMOVE_ITEMS_NOT_SPECIFIED,
                    force_code=reports.codes.FORCE,
                    container_type="property_set",
                    item_type="property",
                    container_id="cib-bootstrap-options",
                )
            ]
        )

    def test_no_properties_specified_forced(self):
        self.config.runner.cib.load()
        self.load_fake_agent_metadata()
        self.config.env.push_cib(
            crm_config=fixture_crm_config_properties(
                [("cib-bootstrap-options", {})]
            )
        )

        self.command({}, [reports.codes.FORCE])
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.ADD_REMOVE_ITEMS_NOT_SPECIFIED,
                    container_type="property_set",
                    item_type="property",
                    container_id="cib-bootstrap-options",
                )
            ]
        )

    def test_no_sets_and_cib_bootstrap_options_id_taken(self):
        self.config.runner.cib.load(
            resources="""
                <resources>
                    <primitive class="ocf" id="cib-bootstrap-options"
                        provider="pacemaker" type="Dummy"/>
                </resources>
            """
        )
        self.env_assist.assert_raise_library_error(
            lambda: self.command({"no-quorum-policy": "freeze"}),
            reports=[
                fixture.error(
                    reports.codes.CANNOT_CREATE_DEFAULT_CLUSTER_PROPERTY_SET,
                    nvset_id="cib-bootstrap-options",
                )
            ],
            expected_in_processor=False,
        )
        self.env_assist.assert_reports([])

    def test_create_cib_bootstrap_options(self):
        self.config.runner.cib.load()
        self.load_fake_agent_metadata()
        self.config.env.push_cib(
            crm_config=fixture_crm_config_properties(
                [("cib-bootstrap-options", {"maintenance-mode": "false"})]
            )
        )

        cluster_property.set_properties(
            self.env_assist.get_env(),
            {"maintenance-mode": "false"},
            [],
        )
        self.env_assist.assert_reports([])

    def _readonly_properties(self, force):
        self.config.runner.cib.load(
            crm_config=fixture_crm_config_properties(
                [
                    (
                        "cib-bootstrap-options",
                        {
                            "cluster-infrastructure": "corosync",
                            "cluster-name": "ClusterName",
                            "dc-version": "2.1.4-5.el9-dc6eb4362e",
                        },
                    )
                ]
            )
        )
        self.load_fake_agent_metadata()
        self.env_assist.assert_raise_library_error(
            lambda: cluster_property.set_properties(
                self.env_assist.get_env(),
                {
                    "cluster-name": "HACluster",
                    "dc-version": "",
                    "have-watchdog": "yes",
                },
                [reports.codes.FORCE] if force else [],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.INVALID_OPTIONS,
                    option_names=[
                        "cluster-name",
                        "dc-version",
                        "have-watchdog",
                    ],
                    allowed=ALLOWED_PROPERTIES,
                    option_type="cluster property",
                    allowed_patterns=[],
                )
            ]
        )

    def test_readonly_properties(self):
        self._readonly_properties(False)

    def test_readonly_properties_forced(self):
        self._readonly_properties(True)

    def test_success(self):
        orig_properties = {
            "batch-limit": "10",
            "enable-acl": "true",
            "stonith-enabled": "true",
        }
        new_properties = {
            "enable-acl": "false",
            "stonith-enabled": "true",
            "maintenance-mode": "false",
        }

        self.config.runner.cib.load(
            crm_config=fixture_crm_config_properties(
                [
                    ("first-set", orig_properties),
                    ("second-set", orig_properties),
                ]
            )
        )
        self.load_fake_agent_metadata()
        self.config.env.push_cib(
            crm_config=fixture_crm_config_properties(
                [
                    ("first-set", new_properties),
                    ("second-set", orig_properties),
                ]
            )
        )

        cluster_property.set_properties(
            self.env_assist.get_env(),
            {
                "batch-limit": "",
                "enable-acl": "false",
                "maintenance-mode": "false",
            },
            [],
        )
        self.env_assist.assert_reports([])

    def test_validator_errors(self):
        self.config.runner.cib.load(
            crm_config=fixture_crm_config_properties(
                [
                    ("cib-bootstrap-options", {}),
                ]
            )
        )
        self.load_fake_agent_metadata()

        self.env_assist.assert_raise_library_error(
            lambda: cluster_property.set_properties(
                self.env_assist.get_env(),
                {
                    "unknown": "property",
                    "enable-acl": "Falsch",
                    "batch-limit": "",
                    "non-existing": "",
                },
                [],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.INVALID_OPTIONS,
                    force_code=reports.codes.FORCE,
                    option_names=["unknown"],
                    allowed=ALLOWED_PROPERTIES,
                    option_type="cluster property",
                    allowed_patterns=[],
                ),
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    force_code=reports.codes.FORCE,
                    option_name="enable-acl",
                    option_value="Falsch",
                    allowed_values=(
                        "a pacemaker boolean value: '0', '1', 'false', 'n', "
                        "'no', "
                        "'off', 'on', 'true', 'y', 'yes'"
                    ),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    reports.codes.ADD_REMOVE_CANNOT_REMOVE_ITEMS_NOT_IN_THE_CONTAINER,
                    force_code=reports.codes.FORCE,
                    container_type=reports.const.ADD_REMOVE_CONTAINER_TYPE_PROPERTY_SET,
                    item_type=reports.const.ADD_REMOVE_ITEM_TYPE_PROPERTY,
                    container_id="cib-bootstrap-options",
                    item_list=["batch-limit", "non-existing"],
                ),
            ]
        )

    def test_validator_errors_forced(self):
        self.config.runner.cib.load(
            crm_config=fixture_crm_config_properties(
                [
                    ("cib-bootstrap-options", {}),
                ]
            )
        )
        self.load_fake_agent_metadata()
        self.config.env.push_cib(
            crm_config=fixture_crm_config_properties(
                [
                    (
                        "cib-bootstrap-options",
                        {
                            "unknown": "property",
                            "enable-acl": "Falsch",
                            "batch-limit": "",
                            "non-existing": "",
                        },
                    ),
                ]
            )
        )

        cluster_property.set_properties(
            self.env_assist.get_env(),
            {
                "unknown": "property",
                "enable-acl": "Falsch",
                "batch-limit": "",
                "non-existing": "",
            },
            [reports.codes.FORCE],
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.INVALID_OPTIONS,
                    option_names=["unknown"],
                    allowed=ALLOWED_PROPERTIES,
                    option_type="cluster property",
                    allowed_patterns=[],
                ),
                fixture.warn(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="enable-acl",
                    option_value="Falsch",
                    allowed_values=(
                        "a pacemaker boolean value: '0', '1', 'false', 'n', "
                        "'no', "
                        "'off', 'on', 'true', 'y', 'yes'"
                    ),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.warn(
                    reports.codes.ADD_REMOVE_CANNOT_REMOVE_ITEMS_NOT_IN_THE_CONTAINER,
                    container_type=reports.const.ADD_REMOVE_CONTAINER_TYPE_PROPERTY_SET,
                    item_type=reports.const.ADD_REMOVE_ITEM_TYPE_PROPERTY,
                    container_id="cib-bootstrap-options",
                    item_list=["batch-limit", "non-existing"],
                ),
            ]
        )


@mock.patch.object(
    settings,
    "pacemaker_api_result_schema",
    rc("pcmk_api_rng/api-result.rng"),
)
class TestPropertySetCrmAttribute(
    TestPropertySetMixin,
    CrmAttributeLoadMetadataMixin,
    CrmAttributeMetadataErrorMixin,
    TestCase,
):
    pass


class TestGetProperties(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def command(self, evaluate_expired=False):
        return cluster_property.get_properties(
            self.env_assist.get_env(),
            evaluate_expired=evaluate_expired,
        )

    def test_no_properties_configured(self):
        self.config.runner.cib.load()
        self.assertEqual(self.command(), ListCibNvsetDto(nvsets=[]))

    def test_empty_cluster_property_set(self):
        self.config.runner.cib.load(
            crm_config=fixture_crm_config_properties([("set_id", {})])
        )
        self.assertEqual(
            self.command(),
            ListCibNvsetDto(
                nvsets=[
                    CibNvsetDto(id="set_id", options={}, rule=None, nvpairs=[])
                ]
            ),
        )

    def test_cluster_property_set_with_properties(self):
        self.config.runner.cib.load(
            crm_config=fixture_crm_config_properties(
                [("set_id", {"prop1": "val1", "prop2": "val2"})],
                score_list=[100],
            )
        )
        self.assertEqual(
            self.command(),
            ListCibNvsetDto(
                nvsets=[
                    CibNvsetDto(
                        id="set_id",
                        options={"score": "100"},
                        rule=None,
                        nvpairs=[
                            CibNvpairDto(
                                id="set_id-prop1", name="prop1", value="val1"
                            ),
                            CibNvpairDto(
                                id="set_id-prop2", name="prop2", value="val2"
                            ),
                        ],
                    )
                ]
            ),
        )

    def test_more_cluster_property_sets(self):
        self.config.runner.cib.load(
            crm_config=fixture_crm_config_properties(
                [
                    ("set_id", {"prop1": "val1", "prop2": "val2"}),
                    ("set_id2", {"prop3": "val3", "prop4": "val4"}),
                ],
                score_list=[100, 200],
            )
        )
        self.assertEqual(
            self.command(),
            ListCibNvsetDto(
                nvsets=[
                    CibNvsetDto(
                        id="set_id",
                        options={"score": "100"},
                        rule=None,
                        nvpairs=[
                            CibNvpairDto(
                                id="set_id-prop1", name="prop1", value="val1"
                            ),
                            CibNvpairDto(
                                id="set_id-prop2", name="prop2", value="val2"
                            ),
                        ],
                    ),
                    CibNvsetDto(
                        id="set_id2",
                        options={"score": "200"},
                        rule=None,
                        nvpairs=[
                            CibNvpairDto(
                                id="set_id2-prop3", name="prop3", value="val3"
                            ),
                            CibNvpairDto(
                                id="set_id2-prop4", name="prop4", value="val4"
                            ),
                        ],
                    ),
                ]
            ),
        )

    def test_cib_error(self):
        self.config.runner.cib.load(returncode=1, stderr="error")
        self.env_assist.assert_raise_library_error(
            self.command,
            reports=[
                fixture.error(reports.codes.CIB_LOAD_ERROR, reason="error")
            ],
            expected_in_processor=False,
        )
        self.env_assist.assert_reports([])

    @mock.patch(
        "pcs.lib.cib.rule.in_effect.has_rule_in_effect_status_tool",
        lambda: True,
    )
    def test_evaluate_expired_but_no_set_rule(self):
        self.config.runner.cib.load(
            crm_config=fixture_crm_config_properties([("set_id", {})])
        )
        self.assertEqual(
            self.command(evaluate_expired=True),
            ListCibNvsetDto(
                nvsets=[
                    CibNvsetDto(id="set_id", options={}, rule=None, nvpairs=[])
                ]
            ),
        )

    @mock.patch(
        "pcs.lib.cib.rule.in_effect.has_rule_in_effect_status_tool",
        lambda: False,
    )
    def test_evaluate_expired_no_status_tool(self):
        self.config.runner.cib.load(
            crm_config=fixture_crm_config_properties([("set_id", {})])
        )
        self.assertEqual(
            self.command(evaluate_expired=True),
            ListCibNvsetDto(
                nvsets=[
                    CibNvsetDto(id="set_id", options={}, rule=None, nvpairs=[])
                ]
            ),
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.RULE_IN_EFFECT_STATUS_DETECTION_NOT_SUPPORTED,
                )
            ]
        )


class TestGetPropertiesMetadataMixin:
    _load_cib_when_metadata_error = False

    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def metadata_error_command(self):
        return self.command()

    def command(self):
        return cluster_property.get_properties_metadata(
            self.env_assist.get_env()
        )

    def _load_fake_agent_test_metadata(self):
        raise NotImplementedError

    def test_get_properties_metadata(self):
        self._load_fake_agent_test_metadata()
        self.assertEqual(
            self.command(),
            ClusterPropertyMetadataDto(
                properties_metadata=[
                    ResourceAgentParameterDto(
                        name="property-name",
                        shortdesc="shortdesc",
                        longdesc="shortdesc.\nlongdesc",
                        type="boolean",
                        default="false",
                        enum_values=None,
                        required=False,
                        advanced=False,
                        deprecated=False,
                        deprecated_by=[],
                        deprecated_desc=None,
                        unique_group=None,
                        reloadable=False,
                    ),
                    ResourceAgentParameterDto(
                        name="enum-property",
                        shortdesc="same desc",
                        longdesc=None,
                        type="select",
                        default="stop",
                        enum_values=[
                            "stop",
                            "freeze",
                            "ignore",
                            "demote",
                            "suicide",
                        ],
                        required=False,
                        advanced=False,
                        deprecated=False,
                        deprecated_by=[],
                        deprecated_desc=None,
                        unique_group=None,
                        reloadable=False,
                    ),
                    ResourceAgentParameterDto(
                        name="advanced-property",
                        shortdesc="advanced shortdesc",
                        longdesc="advanced shortdesc.\nlongdesc",
                        type="boolean",
                        default="false",
                        enum_values=None,
                        required=False,
                        advanced=True,
                        deprecated=False,
                        deprecated_by=[],
                        deprecated_desc=None,
                        unique_group=None,
                        reloadable=False,
                    ),
                ],
                readonly_properties=READONLY_PROPERTIES,
            ),
        )
        self.env_assist.assert_reports([])


@mock.patch.object(
    settings,
    "pacemaker_api_result_schema",
    rc("pcmk_api_rng/api-result.rng"),
)
class TestGetPropertiesMetadataCrmAttribute(
    TestGetPropertiesMetadataMixin, CrmAttributeMetadataErrorMixin, TestCase
):
    def _load_fake_agent_test_metadata(self):
        self.config.runner.pcmk.is_crm_attribute_list_options_supported(
            is_supported=True
        )
        self.config.runner.pcmk.load_crm_attribute_metadata(
            agent_name="cluster-options",
            stdout="""
                <pacemaker-result api-version="2.38" request="crm_attribute --list-options=cluster --output-as xml">
                  <resource-agent name="cluster-options" version="2.1.5-7.el9">
                    <version>1.1</version>
                    <longdesc lang="en">agent longdesc</longdesc>
                    <shortdesc lang="en">agent shortdesc</shortdesc>
                    <parameters>
                      <parameter name="property-name" advanced="0" generated="0">
                        <longdesc lang="en">longdesc</longdesc>
                        <shortdesc lang="en">shortdesc</shortdesc>
                        <content type="boolean" default="false"/>
                      </parameter>
                      <parameter name="enum-property" advanced="0" generated="0">
                        <longdesc lang="en">same desc</longdesc>
                        <shortdesc lang="en">same desc</shortdesc>
                        <content type="select" default="stop">
                          <option value="stop" />
                          <option value="freeze" />
                          <option value="ignore" />
                          <option value="demote" />
                          <option value="suicide" />
                        </content>
                      </parameter>
                      <parameter name="advanced-property" advanced="0" generated="0">
                        <longdesc lang="en">longdesc</longdesc>
                        <shortdesc lang="en">
                          *** Advanced Use Only *** advanced shortdesc
                        </shortdesc>
                        <content type="boolean" default="false"/>
                      </parameter>
                    </parameters>
                  </resource-agent>
                  <status code="0" message="OK"/>
                </pacemaker-result>
            """,
        )


class RemoveClusterName(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.runner_args = [
            settings.cibadmin_exec,
            "--delete-all",
            "--force",
            "--xpath=/cib/configuration/crm_config/cluster_property_set/nvpair[@name='cluster-name']",
        ]
        self.cib_path = os.path.join(settings.cib_dir, "cib.xml")
        self.runner_env = {"CIB_file": self.cib_path}

    def test_success(self):
        self.config.services.is_running("pacemaker", return_value=False)
        self.config.fs.exists(self.cib_path)
        self.config.runner.place(self.runner_args, env=self.runner_env)
        cluster_property.remove_cluster_name(self.env_assist.get_env())

    def test_pacemaker_running(self):
        self.config.services.is_running("pacemaker")
        self.env_assist.assert_raise_library_error(
            lambda: cluster_property.remove_cluster_name(
                self.env_assist.get_env()
            )
        )
        self.env_assist.assert_reports(
            [fixture.error(reports.codes.PACEMAKER_RUNNING)]
        )

    def test_no_cib_xml(self):
        self.config.services.is_running("pacemaker", return_value=False)
        self.config.fs.exists(self.cib_path, return_value=False)
        self.env_assist.assert_raise_library_error(
            lambda: cluster_property.remove_cluster_name(
                self.env_assist.get_env()
            )
        )
        self.env_assist.assert_reports(
            [fixture.error(reports.codes.CIB_XML_MISSING)]
        )

    def test_runner_failed(self):
        self.config.services.is_running("pacemaker", return_value=False)
        self.config.fs.exists(self.cib_path)
        self.config.runner.place(
            self.runner_args,
            env=self.runner_env,
            returncode=1,
            stdout="foo",
            stderr="bar",
        )
        self.env_assist.assert_raise_library_error(
            lambda: cluster_property.remove_cluster_name(
                self.env_assist.get_env()
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.CIB_CLUSTER_NAME_REMOVAL_FAILED,
                    reason="bar\nfoo",
                )
            ]
        )
