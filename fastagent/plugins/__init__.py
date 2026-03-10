"""Plugin utilities."""

from fastagent.plugins.manifest import (
    load_manifest,
    remove_plugin,
    save_manifest,
    set_plugin_enabled,
    upsert_plugin,
)
from fastagent.plugins.registry import (
    find_registry_plugin,
    install_registry_plugin,
    load_registry,
)
from fastagent.plugins.audit import (
    DEFAULT_AUDIT_SECRET,
    sign_audit_event,
    verify_audit_event,
    verify_audit_log,
)
from fastagent.plugins.signing import (
    generate_keypair,
    load_private_key,
    load_public_key,
    public_key_to_base64,
    sha256_hex,
    sign_payload,
    verify_signature,
)
from fastagent.plugins.trust import (
    DEFAULT_TRUST_POLICY,
    load_trust_policy,
    normalize_trust_policy,
    save_trust_policy,
)

__all__ = [
    "load_manifest",
    "save_manifest",
    "upsert_plugin",
    "remove_plugin",
    "set_plugin_enabled",
    "load_registry",
    "find_registry_plugin",
    "install_registry_plugin",
    "DEFAULT_AUDIT_SECRET",
    "sign_audit_event",
    "verify_audit_event",
    "verify_audit_log",
    "sha256_hex",
    "load_private_key",
    "load_public_key",
    "public_key_to_base64",
    "generate_keypair",
    "sign_payload",
    "verify_signature",
    "DEFAULT_TRUST_POLICY",
    "load_trust_policy",
    "normalize_trust_policy",
    "save_trust_policy",
]
