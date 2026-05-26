from pipeline.domain.normalizer import normalize_company_name, normalize_person_name


def test_normalize_company_strips_suffix_and_country():
    assert normalize_company_name("Roche (Switzerland)") == "roche"
    assert normalize_company_name("BioNTech SE") == "biontech"
    assert normalize_company_name("Idorsia Pharmaceuticals Ltd") == "idorsia pharmaceuticals"


def test_normalize_person_name():
    assert normalize_person_name("Sandra Müller") == "sandra muller"
