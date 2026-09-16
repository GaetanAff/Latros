import orjson
import pytest

from latros.common import LatrosError
from latros.knowledge.importers import Knowledge, import_ontology, import_orphadata, import_registry
from latros.knowledge.store import build_snapshot, load_manifest, read_tables, snapshot_path


def test_bilingual_records_mapping_and_provenance(built):
    root, _ = built
    manifest, tables = read_tables(root, "test")
    assert manifest["tables"]["disease_phenotype_assertion"]["rows"] == 8
    assert {t["language"] for t in tables["term"]} == {"en", "fr"}
    assert any(t["text"] == "Invented alias" for t in tables["term"])
    relations = {(m["target_external_id"], m["relation"]) for m in tables["mapping"]}
    assert ("ORPHA:900001", "exactMatch") in relations
    assert ("ORPHA:900003", "xref") in relations
    assert ("ORPHA:900003", "exactMatch") not in relations
    for assertion in tables["disease_phenotype_assertion"]:
        assert orjson.loads(assertion["languages_json"]) == ["en", "fr"]
        evidence = orjson.loads(assertion["provenance_json"])
        assert len(evidence) == 2
        assert all(p["sha256"] and p["source_record_id"] for p in evidence)


def test_reproducibility_and_read_only(built):
    import duckdb

    root, registry = built
    first = load_manifest(root, "test")
    second = build_snapshot(root, registry, "again")
    assert first["tables"] == second["tables"]
    assert first["content_sha256"] == second["content_sha256"]
    assert "database_sha256" not in first  # Container layout is not a canonical identity.
    assert (snapshot_path(root, "test").parent / "integrity.json").is_file()
    assert first == build_snapshot(root, registry, "test")
    with duckdb.connect(str(snapshot_path(root, "test")), read_only=True) as db:
        with pytest.raises(duckdb.InvalidInputException):
            db.execute("DELETE FROM concept")


def test_snapshot_checksum_detects_corruption(built):
    root, _ = built
    snapshot_path(root, "test").write_bytes(b"corrupted")
    with pytest.raises(LatrosError, match="checksum"):
        load_manifest(root, "test")


def test_missing_or_wrong_runtime_receipt_rejected(built):
    from latros.common import write_json

    root, _ = built
    receipt = snapshot_path(root, "test").parent / "integrity.json"
    write_json(receipt, {"snapshot": "not-test"})
    with pytest.raises(LatrosError, match="checksum"):
        load_manifest(root, "test")
    receipt.unlink()
    with pytest.raises(LatrosError, match="receipt"):
        load_manifest(root, "test")


def test_build_unknown_hpo_fails_without_publication(tmp_path, registry):
    from latros.common import sha256

    source = next(s for s in registry.sources if s.id == "orphadata")
    path = tmp_path / "data/raw/orphadata/test-v1/en_product4.xml"
    path.write_bytes(path.read_bytes().replace(b"HP:9000001", b"HP:8888888"))
    source.artifacts[0].sha256 = sha256(path)
    with pytest.raises(LatrosError, match="Unresolved"):
        build_snapshot(tmp_path, registry, "invalid")
    assert not snapshot_path(tmp_path, "invalid").exists()
    assert not (tmp_path / "manifests/invalid.json").exists()
    assert (tmp_path / "data/failures/invalid.json").exists()


def test_duplicate_assertion_and_bilingual_conflict(tmp_path, registry):
    kb = Knowledge()
    hpo = registry.sources[0]
    import_ontology(kb, tmp_path / "data/raw/hpo/test-v1/hp.json", hpo, hpo.artifacts[0])
    source = registry.sources[2]
    path = tmp_path / "data/raw/orphadata/test-v1/en_product4.xml"
    from lxml import etree

    tree = etree.parse(str(path))
    entries = list(tree.iter("HPODisorderAssociation"))
    entries[1].set("id", entries[0].get("id"))
    path.write_bytes(etree.tostring(tree))
    with pytest.raises(LatrosError, match="Duplicate"):
        import_orphadata(kb, path, source, source.artifacts[0])


def test_missing_language_and_conflicting_translation(tmp_path, registry):
    path = tmp_path / "data/raw/orphadata/test-v1/fr_product4.xml"
    path.write_bytes(path.read_bytes().replace(b'id="28412"', b'id="28433"'))
    with pytest.raises(LatrosError, match="Conflicting EN/FR"):
        import_registry(tmp_path, registry)


def test_obsolete_alternate_and_inactive(tmp_path, registry):
    kb = Knowledge()
    source = registry.sources[0]
    import_ontology(kb, tmp_path / "data/raw/hpo/test-v1/hp.json", source, source.artifacts[0])
    assert kb.resolve_hpo("HP:9999998") == kb.resolve_hpo("HP:9000001")
    assert kb.resolve_hpo("HP:9999901") == kb.resolve_hpo("HP:9000001")
    assert kb.resolve_hpo("HP:9999999") == kb.concepts["HP:9999999"]["id"]
    assert any("Inactive" in message for message in kb.warnings)


def test_raw_checksum_and_path_traversal(tmp_path, registry):
    with pytest.raises(LatrosError, match="identifier"):
        build_snapshot(tmp_path, registry, "../escape")
    (tmp_path / "data/raw/hpo/test-v1/hp.json").write_bytes(b"tampered")
    with pytest.raises(LatrosError, match="corrupt source"):
        build_snapshot(tmp_path, registry, "bad-hash")


def test_clean_clone_rebuilds_from_tracked_manifest(built, tmp_path_factory):
    import shutil

    root, registry = built
    clone = tmp_path_factory.mktemp("clone")
    shutil.copytree(root / "data/raw", clone / "data/raw")
    shutil.copytree(root / "manifests", clone / "manifests")
    before = (clone / "manifests/test.json").read_bytes()
    rebuilt = build_snapshot(clone, registry, "test")
    assert rebuilt == load_manifest(root, "test")
    assert (clone / "manifests/test.json").read_bytes() == before


def test_pinned_manifest_mismatch_refuses_publication(built, tmp_path_factory):
    import shutil

    from latros.common import write_json

    root, registry = built
    clone = tmp_path_factory.mktemp("clone")
    shutil.copytree(root / "data/raw", clone / "data/raw")
    expected = load_manifest(root, "test")
    expected["tables"]["concept"]["rows"] += 1
    write_json(clone / "manifests/test.json", expected)
    with pytest.raises(LatrosError, match="Reconstruction differs"):
        build_snapshot(clone, registry, "test")
    assert not snapshot_path(clone, "test").exists()


def test_untranslated_labels_not_claimed_french(tmp_path, registry):
    from lxml import etree

    path = tmp_path / "data/raw/orphadata/test-v1/fr_product4.xml"
    tree = etree.parse(str(path))
    for term in tree.iter("HPOTerm"):
        term.text = term.text.replace("fr invented", "en invented")
    path.write_bytes(etree.tostring(tree))
    kb = import_registry(tmp_path, registry)
    assert not any(t["language"] == "fr" and "HP:" in t["text"] for t in kb.rows["term"].values())
    assert any(t["language"] == "fr" for t in kb.rows["term"].values())


def test_provenance_and_cycle_validation(tmp_path, registry):
    from latros.knowledge.importers import validate_knowledge

    kb = import_registry(tmp_path, registry)
    assertion = next(iter(kb.rows["disease_phenotype_assertion"].values()))
    saved = assertion["provenance_json"]
    assertion["provenance_json"] = "[]"
    with pytest.raises(LatrosError, match="provenance"):
        validate_knowledge(kb)
    assertion["provenance_json"] = saved
    edge = next(iter(kb.rows["hierarchy_edge"].values()))
    edge["parent_id"] = edge["child_id"]
    with pytest.raises(LatrosError, match="cycle"):
        validate_knowledge(kb)


def test_xml_dtd_refused(tmp_path, registry):
    path = tmp_path / "data/raw/orphadata/test-v1/fr_product4.xml"
    path.write_bytes(b'<!DOCTYPE JDBOR [<!ENTITY test "blocked">]>' + path.read_bytes())
    with pytest.raises(LatrosError, match="DTDs"):
        import_registry(tmp_path, registry)
