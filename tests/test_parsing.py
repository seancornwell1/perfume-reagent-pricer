import pytest

from pricer.config import load_reagents
from pricer.matching import match
from pricer.units import pack_grams, parse_concentration, parse_size

TARGET, REAGENTS = load_reagents("reagents.yaml")
R = {r.name: r for r in REAGENTS}


@pytest.mark.parametrize("text,unit,amount", [
    ("5g", "g", 5), ("10 Grams", "g", 10), ("1 kg", "kg", 1), ("4ml", "ml", 4),
    ("15 mL bottle", "ml", 15), ("1/2 oz", "oz", 0.5), ("1 fl oz", "floz", 1),
    ("2 lbs", "lb", 2), ("Size: 25 gr", "g", 25), ("0,5 kg", "kg", 0.5),
])
def test_parse_size(text, unit, amount):
    s = parse_size(text)
    assert s.unit == unit and s.amount == pytest.approx(amount)


def test_parse_size_skips_percent_and_missing():
    assert parse_size("Default Title") is None
    assert parse_size("10% in DPG") is None
    assert parse_size("10% in DPG, 30 g").amount == 30


def test_volume_converted_with_density():
    g, flags = pack_grams(parse_size("4 ml"), 0.945)
    assert g == pytest.approx(3.78)
    assert flags


@pytest.mark.parametrize("text,conc,diluted", [
    ("Beta Ionone", 1.0, False),
    ("Beta Ionone 10% in DPG", 0.10, True),
    ("Damascone beta 1%", 0.01, True),
    ("Ethylene Brassylate 98%", 1.0, False),
    ("Ethylene Brassylate min. 95%", 1.0, False),
    ("Delta Decalactone (dilution)", None, True),
    ("Allyl amyl glycolate 100%", 1.0, False),
])
def test_concentration(text, conc, diluted):
    c, d = parse_concentration(text)
    assert d is diluted
    assert (c is None and conc is None) or c == pytest.approx(conc)


@pytest.mark.parametrize("reagent,title,ok", [
    ("Beta-ionone", "Ionone Beta", True),
    ("Beta-ionone", "β-Ionone", True),
    ("Beta-ionone", "b-ionone (Symrise)", True),
    ("Beta-ionone", "Alpha Ionone", False),
    ("Beta-ionone", "Methyl Ionone Gamma", False),
    ("Beta-ionone", "Ionone Alpha Beta mix", False),
    ("Beta-ionone", "Dihydro Beta Ionone", False),
    ("Beta-damascone", "Damascone Beta (Firmenich)", True),
    ("Beta-damascone", "Beta Damascenone", False),
    ("Beta-damascone", "Damascone Alpha", False),
    ("Delta-decalactone", "Decalactone Delta FG", True),
    ("Delta-decalactone", "δ-Decalactone", True),
    ("Delta-decalactone", "Gamma Decalactone", False),
    ("Delta-decalactone", "Delta Dodecalactone", False),
    ("Ethylene brassylate", "Ethylene Brassylate (Musk T)", True),
    ("Ethylene brassylate", "Musk T", True),
    ("Ethylene brassylate", "Musk Ketone", False),
    ("Allyl amyl glycolate", "Allyl Amyl Glycolate", True),
    ("Allyl amyl glycolate", "AAG", True),
    ("Allyl amyl glycolate", "Allyl Caproate", False),
    ("Nutmeg essential oil", "Nutmeg Essential Oil (Indonesia)", True),
    ("Nutmeg essential oil", "Nutmeg CO2 Extract", False),
    ("Nutmeg essential oil", "Nutmeg Fragrance Oil", False),
    ("Nutmeg essential oil", "Mace Oil", False),
    ("Delta-decalactone", "Lactone C10 (705-86-2)", True),
])
def test_match(reagent, title, ok):
    assert bool(match(R[reagent], title)) is ok
