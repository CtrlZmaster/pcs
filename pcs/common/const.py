from typing import NewType

from pcs.common.tools import Version

PcmkRoleType = NewType("PcmkRoleType", str)
PcmkStatusRoleType = NewType("PcmkStatusRoleType", str)
PcmkOnFailAction = NewType("PcmkOnFailAction", str)
PcmkAction = NewType("PcmkAction", str)
ResourceIdType = NewType("ResourceIdType", str)

INFINITY = "INFINITY"
PCMK_ROLE_STARTED = PcmkRoleType("Started")
PCMK_ROLE_STOPPED = PcmkRoleType("Stopped")
PCMK_ROLE_PROMOTED = PcmkRoleType("Promoted")
PCMK_ROLE_UNPROMOTED = PcmkRoleType("Unpromoted")
PCMK_ROLE_PROMOTED_LEGACY = PcmkRoleType("Master")
PCMK_ROLE_UNPROMOTED_LEGACY = PcmkRoleType("Slave")
PCMK_STATUS_ROLE_STARTED = PcmkStatusRoleType("Started")
PCMK_STATUS_ROLE_STOPPED = PcmkStatusRoleType("Stopped")
PCMK_STATUS_ROLE_PROMOTED = PcmkStatusRoleType("Promoted")
PCMK_STATUS_ROLE_UNPROMOTED = PcmkStatusRoleType("Unpromoted")
PCMK_STATUS_ROLE_STARTING = PcmkStatusRoleType("Starting")
PCMK_STATUS_ROLE_STOPPING = PcmkStatusRoleType("Stopping")
PCMK_STATUS_ROLE_MIGRATING = PcmkStatusRoleType("Migrating")
PCMK_STATUS_ROLE_PROMOTING = PcmkStatusRoleType("Promoting")
PCMK_STATUS_ROLE_DEMOTING = PcmkStatusRoleType("Demoting")
PCMK_ON_FAIL_ACTION_IGNORE = PcmkOnFailAction("ignore")
PCMK_ON_FAIL_ACTION_BLOCK = PcmkOnFailAction("block")
PCMK_ON_FAIL_ACTION_DEMOTE = PcmkOnFailAction("demote")
PCMK_ON_FAIL_ACTION_STOP = PcmkOnFailAction("stop")
PCMK_ON_FAIL_ACTION_RESTART = PcmkOnFailAction("restart")
PCMK_ON_FAIL_ACTION_STANDBY = PcmkOnFailAction("standby")
PCMK_ON_FAIL_ACTION_FENCE = PcmkOnFailAction("fence")
PCMK_ON_FAIL_ACTION_RESTART_CONTAINER = PcmkOnFailAction("restart-container")
PCMK_ROLES_RUNNING = (
    PCMK_ROLE_STARTED,
    PCMK_ROLE_PROMOTED,
    PCMK_ROLE_UNPROMOTED,
)
PCMK_ROLES_RUNNING_WITH_LEGACY = PCMK_ROLES_RUNNING + (
    PCMK_ROLE_PROMOTED_LEGACY,
    PCMK_ROLE_UNPROMOTED_LEGACY,
)
PCMK_ROLES = (PCMK_ROLE_STOPPED,) + PCMK_ROLES_RUNNING
PCMK_ROLES_WITH_LEGACY = (PCMK_ROLE_STOPPED,) + PCMK_ROLES_RUNNING_WITH_LEGACY
PCMK_STATUS_ROLES_RUNNING = (
    PCMK_STATUS_ROLE_STARTED,
    PCMK_STATUS_ROLE_PROMOTED,
    PCMK_STATUS_ROLE_UNPROMOTED,
)
PCMK_STATUS_ROLES_PENDING = (
    PCMK_STATUS_ROLE_STARTING,
    PCMK_STATUS_ROLE_STOPPING,
    PCMK_STATUS_ROLE_MIGRATING,
    PCMK_STATUS_ROLE_PROMOTING,
    PCMK_STATUS_ROLE_DEMOTING,
)
PCMK_STATUS_ROLES = (
    PCMK_STATUS_ROLES_RUNNING
    + PCMK_STATUS_ROLES_PENDING
    + (PCMK_STATUS_ROLE_STOPPED,)
)
PCMK_ACTION_START = PcmkAction("start")
PCMK_ACTION_STOP = PcmkAction("stop")
PCMK_ACTION_PROMOTE = PcmkAction("promote")
PCMK_ACTION_DEMOTE = PcmkAction("demote")
PCMK_ACTIONS = (
    PCMK_ACTION_START,
    PCMK_ACTION_STOP,
    PCMK_ACTION_PROMOTE,
    PCMK_ACTION_DEMOTE,
)
PCMK_NEW_ROLES_CIB_VERSION = Version(3, 7, 0)
# CIB schema which supports new rules syntax and options defined in Pacemaker 3.
# Lower schema is not supported for rules by pcs, as we support Pacemaker 3+
# only in pcs-0.12.
PCMK_RULES_PCMK3_SYNTAX_CIB_VERSION = Version(3, 9, 0)
PCMK_ON_FAIL_DEMOTE_CIB_VERSION = Version(3, 4, 0)

RESOURCE_ID_TYPE_PLAIN = ResourceIdType("resource_id_plain")
RESOURCE_ID_TYPE_REGEXP = ResourceIdType("resource_id_regexp")
