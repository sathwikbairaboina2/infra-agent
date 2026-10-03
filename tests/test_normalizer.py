from __future__ import annotations

import pytest

from infra_agent.normalizer import NormalizeError, normalize_terraform
from tests.factories import LS, changeset, plan, provider_cfg, rc


def test_noop_and_read_and_data_are_excluded():
    data = rc("data.aws_x.y", "aws_x", ["read"])
    data["mode"] = "data"
    cs = changeset(
        resource_changes=[
            rc("aws_s3_bucket.a", "aws_s3_bucket", ["no-op"]),
            rc("aws_s3_bucket.b", "aws_s3_bucket", ["read"]),
            data,
            rc("aws_s3_bucket.c", "aws_s3_bucket", ["create"], after={"bucket": "c"}),
        ]
    )
    assert [c["address"] for c in cs["changes"]] == ["aws_s3_bucket.c"]
    assert cs["tool"] == "terraform"


@pytest.mark.parametrize("actions", [["delete", "create"], ["create", "delete"]])
def test_replace_detected_in_both_orders(actions):
    cs = changeset(resource_changes=[rc("aws_dynamodb_table.t", "aws_dynamodb_table", actions)])
    assert cs["changes"][0]["replace"] is True
    assert cs["stats"] == {"create": 0, "update": 0, "delete": 0, "replace": 1}


def test_stats_and_fields():
    cs = changeset(
        resource_changes=[
            rc("a.one", "a", ["create"], after={"x": 1}),
            rc("a.two", "a", ["update"], before={"x": 1}, after={"x": 2}),
            rc("a.three", "a", ["delete"], before={"x": 1}),
        ]
    )
    assert cs["stats"] == {"create": 1, "update": 1, "delete": 1, "replace": 0}
    first = cs["changes"][0]
    assert first["module_address"] is None
    assert first["after_unknown"] == {}
    assert cs["plan_sha256"] == "0" * 64
    assert cs["base_commit"] == "b" * 40
    assert cs["patch_sha256"] == "1" * 64


def test_providers_extracted_including_alias():
    cs = changeset(
        providers={
            "aws": provider_cfg(),
            "aws.real": provider_cfg(
                endpoints=None, region="us-west-2", key="aws.real", alias="real"
            ),
        }
    )
    by_key = {p["key"]: p for p in cs["providers"]}
    assert by_key["aws"]["endpoints"]["s3"] == LS
    assert by_key["aws"]["region"] == "us-east-1"
    assert by_key["aws"]["alias"] is None
    assert by_key["aws.real"]["alias"] == "real"
    assert by_key["aws.real"]["endpoints"] == {}
    assert by_key["aws.real"]["region"] == "us-west-2"


def test_reference_values_become_none():
    cfg = provider_cfg()
    cfg["expressions"]["region"] = {"references": ["var.region"]}
    cs = changeset(providers={"aws": cfg})
    assert cs["providers"][0]["region"] is None


def test_provisioners_found_in_nested_modules():
    inner = {
        "resources": [{"address": "aws_s3_bucket.x", "provisioners": [{"type": "local-exec"}]}]
    }
    mid = {"resources": [], "module_calls": {"b": {"source": "./b", "module": inner}}}
    cs = changeset(module_calls={"a": {"source": "./a", "module": mid}})
    assert cs["provisioners"] == [
        {"address": "module.a.module.b.aws_s3_bucket.x", "type": "local-exec"}
    ]


def test_module_sources():
    cs = changeset(
        module_calls={
            "a": {"source": "./a", "module": {"resources": []}},
            "vpc": {"source": "terraform-aws-modules/vpc/aws", "module": {"resources": []}},
        }
    )
    assert {m["address"]: m["source"] for m in cs["module_calls"]} == {
        "module.a": "./a",
        "module.vpc": "terraform-aws-modules/vpc/aws",
    }


def test_root_resource_provisioner():
    cs = changeset(
        resources_cfg=[{"address": "aws_s3_bucket.x", "provisioners": [{"type": "local-exec"}]}]
    )
    assert cs["provisioners"] == [{"address": "aws_s3_bucket.x", "type": "local-exec"}]


def test_errored_plan_raises():
    p = plan()
    p["errored"] = True
    with pytest.raises(NormalizeError):
        normalize_terraform(p, plan_sha256="0" * 64, base_commit="b" * 40, patch_sha256="1" * 64)


def test_missing_keys_give_empty_lists():
    cs = normalize_terraform({}, plan_sha256="0" * 64, base_commit="b" * 40, patch_sha256="1" * 64)
    assert cs["changes"] == [] and cs["providers"] == []
    assert cs["provisioners"] == [] and cs["module_calls"] == []
    assert cs["stats"] == {"create": 0, "update": 0, "delete": 0, "replace": 0}
