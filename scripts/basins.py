"""The main river basins of Kyrgyzstan: HydroBASINS level 5 ids and our names."""
EE_PROJECT = "suuproject-513820"
HYBAS = "WWF/HydroSHEDS/v1/Basins/hybas_5"
BASINS = {  # HYBAS_ID: (id, towns inside, for the reader)
    4050050350: ("talas", "Talas"),
    4050050300: ("chuy", "Bishkek, Tokmok, Kara-Balta, Kochkor"),
    4050050570: ("issykkul", "Karakol, Cholpon-Ata"),
    4050420980: ("naryn", "Naryn, Toktogul, At-Bashy, Suusamyr"),
    4050421200: ("karadarya", "Osh, Jalal-Abad, Kara-Kulja"),
    4050411990: ("syrdarya_south", "Batken, Kyzyl-Kiya, Isfana, Chatkal"),
    4050438030: ("saryjaz", "Sary-Jaz"),
    4050545530: ("alay", "Alay valley (Kyzyl-Suu)"),
    4050462690: ("aksay", "Ak-Say"),
    4050313840: ("karkyra", "Karkyra"),
}
SOUTH = ("karadarya", "syrdarya_south")  # reservoirs and interstate agreements matter as much as snow


def basins_fc(ee):
    fc = ee.FeatureCollection(HYBAS).filter(ee.Filter.inList("HYBAS_ID", list(BASINS)))
    return fc.map(lambda f: f.set("id", ee.Dictionary({str(k): v[0] for k, v in BASINS.items()}).get(f.getNumber("HYBAS_ID").format("%d"))))
