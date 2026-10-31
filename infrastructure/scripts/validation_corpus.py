"""Validation corpus manifest: real freely-licensed speech (Wikimedia Commons).

Every item: direct URL, exact expected reference where the filename carries
the Lingua Libre transcription, license, and how the reference was derived.
Audio itself is downloaded at validation time (not committed).
Sentence-level references from spoken-Wikipedia openings are APPROXIMATE.
The code-switch clip is CONSTRUCTED from two real clips (honestly labelled).
"""
CORPUS = [
    {"id": "hi_paani", "lang": "hi", "ref": "पानी", "ref_kind": "exact",
     "url": "https://upload.wikimedia.org/wikipedia/commons/8/83/LL-Q1568_%28hin%29-AryamanA-%E0%A4%AA%E0%A4%BE%E0%A4%A8%E0%A5%80.wav",
     "license": "CC BY-SA 4.0 (Lingua Libre via Wikimedia Commons)"},
    {"id": "hi_ladka", "lang": "hi", "ref": "लड़का", "ref_kind": "exact",
     "url": "https://upload.wikimedia.org/wikipedia/commons/e/ec/LL-Q1568_%28hin%29-Blackpeartree_%28Daniel_Mietchen%29-%E0%A4%B2%E0%A4%A1%E0%A4%BC%E0%A4%95%E0%A4%BE.wav",
     "license": "CC BY-SA 4.0 (Lingua Libre via Wikimedia Commons)"},
    {"id": "hi_phal", "lang": "hi", "ref": "फल", "ref_kind": "exact",
     "url": "https://upload.wikimedia.org/wikipedia/commons/b/b3/LL-Q1568_%28hin%29-Jkkku-%E0%A4%AB%E0%A4%B2.wav",
     "license": "CC BY-SA 4.0 (Lingua Libre via Wikimedia Commons)"},
    {"id": "hi_46", "lang": "hi", "ref": "छियालीस", "ref_kind": "exact",
     "url": "https://upload.wikimedia.org/wikipedia/commons/1/17/LL-Q1568_%28hin%29-Mauryaar-%E0%A4%9B%E0%A4%BF%E0%A4%AF%E0%A4%BE%E0%A4%B2%E0%A5%80%E0%A4%B8.wav",
     "license": "CC BY-SA 4.0 (Lingua Libre via Wikimedia Commons)"},
    {"id": "hi_99", "lang": "hi", "ref": "निन्यानवे", "ref_kind": "exact",
     "url": "https://upload.wikimedia.org/wikipedia/commons/c/c4/LL-Q1568_%28hin%29-Mauryaar-%E0%A4%A8%E0%A4%BF%E0%A4%A8%E0%A5%8D%E0%A4%AF%E0%A4%BE%E0%A4%A8%E0%A4%B5%E0%A5%87.wav",
     "license": "CC BY-SA 4.0 (Lingua Libre via Wikimedia Commons)"},
    {"id": "mr_panchsheel", "lang": "mr", "ref": "पंचशील", "ref_kind": "exact",
     "url": "https://upload.wikimedia.org/wikipedia/commons/9/99/LL-Q1571_%28mar%29-Neelima64-%E0%A4%AA%E0%A4%82%E0%A4%9A%E0%A4%B6%E0%A5%80%E0%A4%B2.wav",
     "license": "CC BY-SA 4.0 (Lingua Libre via Wikimedia Commons)"},
    {"id": "mr_pune", "lang": "mr", "ref": "Pune", "ref_kind": "exact",
     "url": "https://upload.wikimedia.org/wikipedia/commons/f/f6/Pune_pronunication.ogg",
     "license": "CC BY-SA 4.0 (Wikimedia Commons)"},
    {"id": "mr_shaniwarwada", "lang": "mr", "ref": "Shaniwarwada", "ref_kind": "exact",
     "url": "https://upload.wikimedia.org/wikipedia/commons/d/d9/Ma-Shaniwarwada.ogg",
     "license": "CC BY-SA / GFDL (Wikimedia Commons)"},
    {"id": "en_water_caltrop", "lang": "en", "ref": "water caltrop", "ref_kind": "exact",
     "url": "https://upload.wikimedia.org/wikipedia/commons/c/c6/LL-Q1860_%28eng%29-Vealhurl-water_caltrop.wav",
     "license": "CC BY-SA 4.0 (Lingua Libre via Wikimedia Commons)"},
    {"id": "en_water_dripping", "lang": "en", "ref": "Water dripping", "ref_kind": "exact",
     "url": "https://upload.wikimedia.org/wikipedia/commons/3/3c/LL-Q1860_%28eng%29-Knites-Water_dripping.wav",
     "license": "CC BY-SA 4.0 (Lingua Libre via Wikimedia Commons)"},
    {"id": "hi_dengue_lead", "lang": "hi", "ref": None, "ref_kind": "approximate",
     "url": "https://upload.wikimedia.org/wikipedia/commons/f/fe/Hindi_Dengue_Introduction.ogg",
     "license": "CC BY-SA / GFDL (Spoken Hindi Wikipedia)",
     "note": "First 25 s; reference is the article opening, approximate."},
]
