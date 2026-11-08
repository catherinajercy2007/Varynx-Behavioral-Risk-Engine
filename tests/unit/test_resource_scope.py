
import pytest

from varynx.engine.resource_scope import (
    capability_is_covered,
    resource_is_within_scope,
    validate_resource_scope,
)


class TestCapabilityIsCovered:
    """Tests for delimiter-aware capability matching."""

    @pytest.mark.parametrize(
        ("requested", "granted", "expected"),
        [
            ("read:files", "read:files", True),
            ("read:files:metadata", "read:files", True),
            ("read:files:metadata:private", "read:files", True),
            ("read:files", "read", True),
            ("read:files", "read:files:metadata", False),
            ("read:filesX", "read:files", False),
            ("write:files", "read:files", False),
            ("", "read:files", False),
            ("read:files", "", False),
        ],
    )
    def test_capability_matching(self, requested, granted, expected):
        assert capability_is_covered(requested, granted) is expected


class TestResourceIsWithinScope:
    """Tests for delimiter-aware resource matching."""

    @pytest.mark.parametrize(
        ("resource", "roots", "expected"),
        [
            ("/data", ["/data"], True),
            ("/data/file.csv", ["/data"], True),
            ("/data/reports/2026.csv", ["/data"], True),
            ("/database/file.csv", ["/data"], False),
            ("/data-private/file.csv", ["/data"], False),
            ("/private/file.csv", ["/data"], False),
            ("/data/file.csv", ["/private", "/data"], True),
            ("/private/file.csv", ["/data", "/private"], True),
            ("/data/file.csv", [], False),
            ("", ["/data"], False),
        ],
    )
    def test_resource_scope_matching(self, resource, roots, expected):
        assert resource_is_within_scope(resource, roots) is expected

    def test_resource_scope_does_not_use_arbitrary_prefix_matching(self):
        assert not resource_is_within_scope(
            "/database/secrets.csv",
            ["/data"],
        )

    def test_resource_scope_requires_delimiter_boundary(self):
        assert not resource_is_within_scope(
            "/data-private/secrets.csv",
            ["/data"],
        )


class TestValidateResourceScope:
    """Tests for fail-closed resource scope validation."""

    @pytest.mark.parametrize(
        "scope",
        [
            {},
            {"resources": []},
            {"resources": ["/data"]},
            {"resources": ["/data", "/reports"]},
            {"resources": ["s3://my-bucket/data"]},
            {"resources": ["arn:aws:iam::123456789012:role/example"]},
        ],
    )
    def test_valid_resource_scopes(self, scope):
        validate_resource_scope(scope)

    @pytest.mark.parametrize(
        "scope",
        [
            None,
            [],
            "resources",
            123,
        ],
    )
    def test_non_dictionary_scope_rejected(self, scope):
        with pytest.raises(ValueError, match="INVALID_RESOURCE_SCOPE"):
            validate_resource_scope(scope)

    @pytest.mark.parametrize(
        "scope",
        [
            {"unexpected": "value"},
            {"resources": ["/data"], "permissions": ["read"]},
            {"wildcard": "*"},
        ],
    )
    def test_unknown_keys_rejected(self, scope):
        with pytest.raises(ValueError, match="INVALID_RESOURCE_SCOPE"):
            validate_resource_scope(scope)

    @pytest.mark.parametrize(
        "resources",
        [
            None,
            "/data",
            "data",
            123,
            {},
        ],
    )
    def test_resources_must_be_a_list(self, resources):
        with pytest.raises(ValueError, match="INVALID_RESOURCE_SCOPE"):
            validate_resource_scope({"resources": resources})

    @pytest.mark.parametrize(
        "resources",
        [
            [""],
            ["   "],
            [None],
            [123],
            [{}],
        ],
    )
    def test_invalid_resource_entries_rejected(self, resources):
        with pytest.raises(ValueError, match="INVALID_RESOURCE_SCOPE"):
            validate_resource_scope({"resources": resources})

    @pytest.mark.parametrize(
        "resources",
        [
            ["*"],
            ["/data/*"],
            ["read:*"],
            ["/private/*/secrets"],
        ],
    )
    def test_wildcard_resource_entries_rejected(self, resources):
        with pytest.raises(ValueError, match="INVALID_RESOURCE_SCOPE"):
            validate_resource_scope({"resources": resources})


class TestMixedResourceContainment:
    """Tests for type-aware resource containment."""

    @pytest.mark.parametrize(
        ("resource", "roots", "expected"),
        [
            ("/data/file.csv", ["/data"], True),
            ("/data/../private/file.csv", ["/data"], False),
            ("/database/file.csv", ["/data"], False),
            ("/data-private/file.csv", ["/data"], False),
            (r"C:\data\file.csv", [r"C:\data"], True),
            (r"C:\database\file.csv", [r"C:\data"], False),
            (r"D:\data\file.csv", [r"C:\data"], False),
            (r"C:\data\..\private\file.csv", [r"C:\data"], False),
            (
                "s3://my-bucket/data/file.csv",
                ["s3://my-bucket/data"],
                True,
            ),
            (
                "s3://my-bucket/database/file.csv",
                ["s3://my-bucket/data"],
                False,
            ),
            (
                "s3://other-bucket/data/file.csv",
                ["s3://my-bucket/data"],
                False,
            ),
            (
                "s3://my-bucket/data/../private/file.csv",
                ["s3://my-bucket/data"],
                True,
            ),
            (
                "s3://my-bucket/data/file.csv",
                ["arn:aws:s3:::my-bucket/data"],
                True,
            ),
            (
                "arn:aws:s3:::my-bucket/data/file.csv",
                ["s3://my-bucket/data"],
                True,
            ),
            (
                "arn:aws:iam::123456789012:role/example",
                ["arn:aws:iam::123456789012:role/example"],
                True,
            ),
            (
                "arn:aws:iam::123456789012:role/example/child",
                ["arn:aws:iam::123456789012:role/example"],
                False,
            ),
            (
                "relative/data/file.csv",
                ["/data"],
                False,
            ),
            (
                "s3://other-bucket/data/file.csv",
                ["/data"],
                False,
            ),
        ],
    )
    def test_mixed_resource_containment(self, resource, roots, expected):
        assert resource_is_within_scope(resource, roots) is expected

    @pytest.mark.parametrize(
        "resource",
        [
            "",
            "relative/path",
            "s3:///missing-bucket/key",
            "s3://my-bucket/key?versionId=123",
            "s3://my-bucket/key#fragment",
            "s3://my-bucket:invalid-port/key",
            "arn:invalid",
            r"C:relative\path",
        ],
    )
    def test_malformed_or_relative_resources_are_denied(self, resource):
        assert not resource_is_within_scope(resource, ["/data"])

    @pytest.mark.parametrize(
        "resource",
        [
            "relative/path",
            "s3:///missing-bucket/key",
            "arn:invalid",
            r"C:relative\path",
        ],
    )
    def test_invalid_resource_roots_are_rejected(self, resource):
        with pytest.raises(ValueError, match="INVALID_RESOURCE_SCOPE"):
            validate_resource_scope({"resources": [resource]})

    def test_mixed_scope_can_contain_multiple_resource_types(self):
        roots = [
            "/data",
            "s3://my-bucket/reports",
            "arn:aws:iam::123456789012:role/example",
        ]

        assert resource_is_within_scope("/data/file.csv", roots)

        assert resource_is_within_scope(
            "s3://my-bucket/reports/annual.csv",
            roots,
        )

        assert resource_is_within_scope(
            "arn:aws:iam::123456789012:role/example",
            roots,
        )

    def test_resource_types_cannot_cross_authorize(self):
        assert not resource_is_within_scope(
            "/data/file.csv",
            ["s3://my-bucket/data"],
        )

        assert not resource_is_within_scope(
            "s3://my-bucket/data/file.csv",
            ["/data"],
        )

    def test_filesystem_and_s3_roots_can_coexist(self):
        roots = [
            "/data",
            "s3://my-bucket/data",
        ]

        assert resource_is_within_scope("/data/file.csv", roots)

        assert resource_is_within_scope(
            "s3://my-bucket/data/file.csv",
            roots,
        )
