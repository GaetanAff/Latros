import gzip
import io
import tarfile
from pathlib import Path

from latros.knowledge.mesh import parse_mesh_descriptors
from latros.knowledge.monarch import iter_monarch_disease_phenotypes


def test_mesh_gzip_parser_preserves_terms_and_hierarchy_keys(tmp_path: Path) -> None:
    artifact = tmp_path / "desc2026.gz"
    payload = b"""<?xml version="1.0"?>
<DescriptorRecordSet>
  <DescriptorRecord>
    <DescriptorUI>D000001</DescriptorUI>
    <DescriptorName><String>Invented condition</String></DescriptorName>
    <TreeNumberList><TreeNumber>C01.100</TreeNumber></TreeNumberList>
    <ConceptList><Concept><TermList>
      <Term><String>Invented condition</String></Term>
      <Term><String>Invented synonym</String></Term>
    </TermList></Concept></ConceptList>
  </DescriptorRecord>
</DescriptorRecordSet>"""
    with gzip.open(artifact, "wb") as stream:
        stream.write(payload)

    records = parse_mesh_descriptors(artifact)

    assert records[0].descriptor_ui == "D000001"
    assert records[0].terms == ["Invented condition", "Invented synonym"]
    assert records[0].tree_numbers == ["C01.100"]


def test_monarch_archive_importer_filters_to_direct_resolvable_disease_hpo(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "monarch-kg.tar.gz"
    header = (
        "id\tpredicate\tcategory\tagent_type\taggregator_knowledge_source\t"
        "knowledge_level\tprimary_knowledge_source\tfile_source\tprovided_by\t"
        "publications\tqualifiers\thas_evidence\tnegated\toriginal_predicate\t"
        "FDA_adverse_event_level\tdisease_context_qualifier\t"
        "object_specialization_qualifier\tobject_category\tsubject_category\t"
        "frequency_qualifier\thas_count\thas_percentage\thas_quotient\thas_total\t"
        "onset_qualifier\tsex_qualifier\thas_attribute\tobject_aspect_qualifier\t"
        "species_context_qualifier\tstage_qualifier\tqualifier\tsubject\tobject\t"
        "original_subject\toriginal_object\n"
    )
    accepted = (
        "edge:1\tbiolink:has_phenotype\t"
        "biolink:DiseaseToPhenotypicFeatureAssociation\tmanual_agent\t"
        "['infores:monarchinitiative']\tknowledge_assertion\tinfores:test\t"
        "test_edges\ttest_edges\tPMID:1\t\tECO:1\tFalse\t\t\t\t\t\t\t\t"
        "1\t50\t0.5\t2\t\t\t\t\t\t\t\tMONDO:0000001\tHP:0000001\t\t\n"
    )
    rejected = accepted.replace("MONDO:0000001", "MONDO:9999999").replace("edge:1", "edge:2")
    edge_bytes = (header + accepted + rejected).encode()
    node_bytes = b"id\tcategory\tname\n"
    with tarfile.open(artifact, "w:gz") as archive:
        for name, content in (
            ("monarch-kg_nodes.tsv", node_bytes),
            ("monarch-kg_edges.tsv", edge_bytes),
        ):
            info = tarfile.TarInfo(name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))

    records = list(
        iter_monarch_disease_phenotypes(
            artifact,
            accepted_subjects={"MONDO:0000001"},
            accepted_objects={"HP:0000001"},
        )
    )

    assert len(records) == 1
    assert records[0].primary_knowledge_source == "infores:test"
    assert records[0].has_percentage == 50.0
    assert records[0].source_locator.endswith("row=2:id=edge:1")
