# Bilingual disease knowledge for the 10 paddy (rice) classes the
# MobileNetV2 transfer-learning model predicts.
# Each entry: short description + first action, in English and Hindi.

PADDY_DISEASE_INFO = {
    "bacterial_leaf_blight": {
        "crop": {"en": "Paddy (Rice)", "hi": "धान (चावल)"},
        "disease": {"en": "Bacterial leaf blight", "hi": "जीवाणु पत्ती झुलसा"},
        "desc": {"en": "Bacterial disease causing yellow-to-white streaks from leaf tips and margins; leaves wilt and turn straw-colored in humid, flooded conditions.",
                 "hi": "जीवाणु रोग—पत्ती की नोक और किनारों से पीली-सफेद धारियाँ; नम व जलभराव वाली स्थिति में पत्तियाँ मुरझाकर भूसे जैसी हो जाती हैं।"},
        "action": {"en": "Use resistant varieties; avoid excess nitrogen; drain fields; apply a copper-based bactericide/streptocycline if severe.",
                   "hi": "रोग-रोधी किस्में उपयोग करें; अधिक नाइट्रोजन न दें; खेत से पानी निकालें; गंभीर हो तो कॉपर/स्ट्रेप्टोसाइक्लिन का छिड़काव करें।"},
    },
    "bacterial_leaf_streak": {
        "crop": {"en": "Paddy (Rice)", "hi": "धान (चावल)"},
        "disease": {"en": "Bacterial leaf streak", "hi": "जीवाणु पत्ती धारी रोग"},
        "desc": {"en": "Bacterial disease producing narrow, water-soaked streaks between leaf veins that turn yellow-brown and look translucent against light.",
                 "hi": "जीवाणु रोग—पत्ती की शिराओं के बीच पतली पानी-भरी धारियाँ जो पीली-भूरी हो जाती हैं और रोशनी में पारदर्शी दिखती हैं।"},
        "action": {"en": "Use certified disease-free seed; avoid field-to-field water flow; balanced fertilization; copper-based bactericide if severe.",
                   "hi": "प्रमाणित रोगमुक्त बीज उपयोग करें; खेतों के बीच पानी बहाव रोकें; संतुलित उर्वरक; गंभीर हो तो कॉपर आधारित जीवाणुनाशक डालें।"},
    },
    "bacterial_panicle_blight": {
        "crop": {"en": "Paddy (Rice)", "hi": "धान (चावल)"},
        "disease": {"en": "Bacterial panicle blight", "hi": "जीवाणु बाली झुलसा"},
        "desc": {"en": "Bacterial disease infecting panicles during hot weather at flowering, causing discolored, empty or chalky grains and poor grain fill.",
                 "hi": "फूल आने के समय गर्म मौसम में जीवाणु रोग—बालियों में दाने खाली, चाकयुक्त या रंगहीन रह जाते हैं और भराव कमज़ोर होता है।"},
        "action": {"en": "Use resistant varieties; avoid excess nitrogen; ensure adequate water during flowering to reduce heat stress; remove infected residue.",
                   "hi": "रोग-रोधी किस्में उपयोग करें; अधिक नाइट्रोजन न दें; फूल आने के समय पर्याप्त पानी दें ताकि गर्मी का तनाव घटे; रोगग्रस्त अवशेष हटाएँ।"},
    },
    "blast": {
        "crop": {"en": "Paddy (Rice)", "hi": "धान (चावल)"},
        "disease": {"en": "Rice blast", "hi": "धान का ब्लास्ट रोग"},
        "desc": {"en": "Fungal disease causing diamond-shaped lesions with gray centers and brown edges on leaves; can also blight the panicle neck, cutting grain yield sharply.",
                 "hi": "फफूंद रोग—पत्तियों पर धूसर केंद्र व भूरे किनारे वाले हीरे के आकार के धब्बे; बाली की गर्दन को भी संक्रमित कर पैदावार को बुरी तरह घटा सकता है।"},
        "action": {"en": "Use resistant varieties; avoid excess nitrogen; apply tricyclazole or a recommended fungicide at first sign; keep drainage balanced.",
                   "hi": "रोग-रोधी किस्में उपयोग करें; अधिक नाइट्रोजन न दें; पहला लक्षण दिखते ही ट्राइसाइक्लाज़ोल या अनुशंसित फफूंदनाशक डालें; खेत में संतुलित जल निकासी रखें।"},
    },
    "brown_spot": {
        "crop": {"en": "Paddy (Rice)", "hi": "धान (चावल)"},
        "disease": {"en": "Brown spot", "hi": "भूरा धब्बा रोग"},
        "desc": {"en": "Fungal disease causing oval brown spots with gray-white centers on leaves and grains, often worse in nutrient-poor or stressed soils.",
                 "hi": "फफूंद रोग—पत्तियों व दानों पर भूरे-सफेद केंद्र वाले अंडाकार भूरे धब्बे; पोषक तत्व-रहित या तनावग्रस्त मिट्टी में अधिक होता है।"},
        "action": {"en": "Improve soil fertility (especially potassium and silicon); use treated seed; apply fungicide if it spreads fast.",
                   "hi": "मिट्टी की उर्वरता सुधारें (विशेषकर पोटाश व सिलिकॉन); उपचारित बीज उपयोग करें; तेज़ी से फैले तो फफूंदनाशक डालें।"},
    },
    "dead_heart": {
        "crop": {"en": "Paddy (Rice)", "hi": "धान (चावल)"},
        "disease": {"en": "Dead heart (stem borer damage)", "hi": "डेड हार्ट (तना छेदक क्षति)"},
        "desc": {"en": "Damage from stem borer larvae tunneling into the stem, killing the central shoot — it dries up, turns brown, and pulls out easily.",
                 "hi": "तना छेदक कीट की सूंडी तने में घुसकर केंद्रीय कल्ले को मार देती है—यह सूखकर भूरा हो जाता है और आसानी से खिंच जाता है।"},
        "action": {"en": "Remove and destroy affected tillers; use pheromone traps; apply a recommended insecticide (e.g., cartap hydrochloride) at early infestation.",
                   "hi": "प्रभावित कल्लों को हटाकर नष्ट करें; फेरोमोन ट्रैप उपयोग करें; शुरुआती संक्रमण पर अनुशंसित कीटनाशक (जैसे कारटैप हाइड्रोक्लोराइड) डालें।"},
    },
    "downy_mildew": {
        "crop": {"en": "Paddy (Rice)", "hi": "धान (चावल)"},
        "disease": {"en": "Downy mildew", "hi": "डाउनी मिल्ड्यू"},
        "desc": {"en": "Oomycete disease causing pale yellow-green streaking and stunted, distorted leaves, favored by cool, wet and humid conditions.",
                 "hi": "फफूंद-सदृश (ओओमाइसीट) रोग—पत्तियों पर हल्की पीली-हरी धारियाँ व बौनापन/विकृति; ठंडे, नम व आर्द्र मौसम में अधिक फैलता है।"},
        "action": {"en": "Use resistant varieties and clean seed; improve field drainage; remove and destroy infected plants; apply a recommended fungicide if severe.",
                   "hi": "रोग-रोधी किस्में व स्वच्छ बीज उपयोग करें; खेत की जल निकासी सुधारें; रोगग्रस्त पौधे हटाकर नष्ट करें; गंभीर हो तो अनुशंसित फफूंदनाशक डालें।"},
    },
    "hispa": {
        "crop": {"en": "Paddy (Rice)", "hi": "धान (चावल)"},
        "disease": {"en": "Rice hispa", "hi": "धान हिस्पा कीट"},
        "desc": {"en": "Insect pest damage — adult beetles scrape the upper leaf surface leaving whitish, translucent streaks, while larvae mine and blotch inside the leaf.",
                 "hi": "कीट क्षति—वयस्क भृंग पत्ती की ऊपरी सतह को खुरचकर सफेद-पारदर्शी धारियाँ बनाते हैं, जबकि सूंडी पत्ती के अंदर सुरंग बनाकर धब्बे डालती है।"},
        "action": {"en": "Clip and destroy affected leaf tips; drain standing water where larvae hide; apply a recommended insecticide if infestation is heavy.",
                   "hi": "प्रभावित पत्ती की नोक काटकर नष्ट करें; खड़े पानी को निकालें जहाँ सूंडी छिपती है; भारी संक्रमण पर अनुशंसित कीटनाशक डालें।"},
    },
    "normal": {
        "crop": {"en": "Paddy (Rice)", "hi": "धान (चावल)"},
        "disease": {"en": "Healthy", "hi": "स्वस्थ"},
        "desc": {"en": "No disease or pest damage detected. Plant looks healthy.",
                 "hi": "कोई रोग या कीट क्षति नहीं मिली। पौधा स्वस्थ दिख रहा है।"},
        "action": {"en": "Keep monitoring; maintain balanced fertilization and proper water management.",
                   "hi": "निगरानी जारी रखें; संतुलित उर्वरक व उचित जल प्रबंधन बनाए रखें।"},
    },
    "tungro": {
        "crop": {"en": "Paddy (Rice)", "hi": "धान (चावल)"},
        "disease": {"en": "Tungro virus", "hi": "टुंग्रो विषाणु रोग"},
        "desc": {"en": "Viral disease spread by green leafhoppers, causing yellow-to-orange leaf discoloration, stunted growth and reduced tillering.",
                 "hi": "हरे फुदके (लीफहॉपर) से फैलने वाला विषाणु रोग—पत्तियाँ पीली-नारंगी हो जाती हैं, वृद्धि रुक जाती है और कल्ले कम बनते हैं।"},
        "action": {"en": "Control leafhopper vectors; use tolerant/resistant varieties; remove and destroy infected plants early; avoid staggered planting nearby.",
                   "hi": "फुदका वाहक कीट को नियंत्रित करें; रोग-सहनशील किस्में उपयोग करें; रोगग्रस्त पौधे जल्दी हटाकर नष्ट करें; आसपास असमान बुवाई से बचें।"},
    },
}

# Ordered class list — MUST match the paddy model's output order exactly.
PADDY_CLASS_NAMES = [
    "bacterial_leaf_blight",
    "bacterial_leaf_streak",
    "bacterial_panicle_blight",
    "blast",
    "brown_spot",
    "dead_heart",
    "downy_mildew",
    "hispa",
    "normal",
    "tungro",
]
