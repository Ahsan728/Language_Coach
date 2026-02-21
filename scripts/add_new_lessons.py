#!/usr/bin/env python3
"""
scripts/add_new_lessons.py
==========================
Append 9 new intermediate/advanced lessons to data/lessons.json
for the vocabulary categories added during the dictionary upgrade.

New lessons 16-24 (same IDs for both French and Spanish):
  16 - Health & Medical
  17 - Home & Living
  18 - Sports & Leisure
  19 - Nature & Environment
  20 - Work & Career
  21 - Shopping & Fashion
  22 - People & Community
  23 - Food & Cooking Advanced
  24 - Travel & Transport Advanced

Usage:
    cd "d:/Software Dev/Language Coach"
    python scripts/add_new_lessons.py
"""

import json, os, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
LESSONS_FILE = os.path.join(DATA_DIR, 'lessons.json')


NEW_FRENCH = [
    {
        "id": 16, "level": "intermediate", "icon": "🏥",
        "title_en": "Health & Medical",
        "title_bn": "স্বাস্থ্য ও চিকিৎসা",
        "title_lang": "Santé et Médecine",
        "description_en": "Essential vocabulary for doctors, pharmacies, symptoms, and staying healthy in France.",
        "description_bn": "ফ্রান্সে ডাক্তার, ফার্মেসি, উপসর্গ এবং সুস্থ থাকার জন্য প্রয়োজনীয় শব্দভান্ডার।",
        "vocabulary_categories": ["health"],
        "tip_en": "In France, say 'J'ai mal à la tête' (I have a headache). Always keep your 'carte vitale' (health card) when visiting a doctor!",
        "tip_bn": "ফ্রান্সে বলুন 'J'ai mal à la tête' (আমার মাথাব্যথা আছে)। ডাক্তারের কাছে যাওয়ার সময় সবসময় আপনার 'carte vitale' (স্বাস্থ্য কার্ড) সাথে রাখুন!"
    },
    {
        "id": 17, "level": "intermediate", "icon": "🏠",
        "title_en": "Home & Living",
        "title_bn": "ঘর ও গৃহস্থালি",
        "title_lang": "La Maison et le Quotidien",
        "description_en": "Furniture, rooms, household items and daily home life vocabulary in French.",
        "description_bn": "ফরাসিতে আসবাবপত্র, ঘরের কক্ষ, গৃহস্থালির জিনিস এবং দৈনন্দিন জীবনের শব্দভান্ডার।",
        "vocabulary_categories": ["home"],
        "tip_en": "The French love their 'salon' (living room) — a central place for family life. 'Faire le ménage' means doing housework.",
        "tip_bn": "ফরাসিরা তাদের 'salon' (বসার ঘর) খুব পছন্দ করেন — পারিবারিক জীবনের কেন্দ্র। 'Faire le ménage' মানে ঘরের কাজ করা।"
    },
    {
        "id": 18, "level": "intermediate", "icon": "⚽",
        "title_en": "Sports & Leisure",
        "title_bn": "খেলাধুলা ও অবসর",
        "title_lang": "Les Sports et les Loisirs",
        "description_en": "Talking about sports, hobbies, and leisure activities in French.",
        "description_bn": "ফরাসিতে খেলাধুলা, শখ এবং অবসর কার্যক্রম সম্পর্কে কথা বলুন।",
        "vocabulary_categories": ["sports"],
        "tip_en": "To say you play a sport: 'Je joue au football' (I play football). For activities: 'Je fais du vélo' (I cycle), 'Je fais de la natation' (I swim).",
        "tip_bn": "খেলা বলতে: 'Je joue au football' (আমি ফুটবল খেলি)। কার্যক্রমের জন্য: 'Je fais du vélo' (আমি সাইকেল চালাই), 'Je fais de la natation' (আমি সাঁতার কাটি)।"
    },
    {
        "id": 19, "level": "intermediate", "icon": "🌿",
        "title_en": "Nature & Environment",
        "title_bn": "প্রকৃতি ও পরিবেশ",
        "title_lang": "La Nature et l'Environnement",
        "description_en": "Describing nature, weather, landscapes, animals, and the environment in French.",
        "description_bn": "ফরাসিতে প্রকৃতি, আবহাওয়া, ভূদৃশ্য, প্রাণী এবং পরিবেশ বর্ণনা করুন।",
        "vocabulary_categories": ["nature"],
        "tip_en": "French weather: 'Il fait beau' (nice weather), 'Il pleut' (it's raining), 'Il neige' (it's snowing). 'Quel temps fait-il?' means 'What's the weather like?'",
        "tip_bn": "ফরাসিতে আবহাওয়া: 'Il fait beau' (ভালো আবহাওয়া), 'Il pleut' (বৃষ্টি হচ্ছে), 'Il neige' (বরফ পড়ছে)। 'Quel temps fait-il?' মানে 'আবহাওয়া কেমন?'"
    },
    {
        "id": 20, "level": "intermediate", "icon": "💼",
        "title_en": "Work & Career",
        "title_bn": "কাজ ও পেশা",
        "title_lang": "Le Travail et la Carrière",
        "description_en": "Professional vocabulary — jobs, workplace, meetings, studies and academic life in French.",
        "description_bn": "পেশাদার শব্দভান্ডার — ফরাসিতে চাকরি, কর্মক্ষেত্র, সভা, পড়াশোনা ও একাডেমিক জীবন।",
        "vocabulary_categories": ["work", "study"],
        "tip_en": "'Je suis chercheur/chercheuse' (I am a researcher). In French academia, 'la thèse' is your PhD thesis, 'le labo' is the lab — essential words!",
        "tip_bn": "'Je suis chercheur/chercheuse' (আমি গবেষক)। ফরাসি একাডেমিয়ায় 'la thèse' হলো আপনার PhD গবেষণা, 'le labo' হলো ল্যাব — এগুলো অপরিহার্য শব্দ!"
    },
    {
        "id": 21, "level": "intermediate", "icon": "🛍️",
        "title_en": "Shopping & Fashion",
        "title_bn": "কেনাকাটা ও ফ্যাশন",
        "title_lang": "Les Achats et la Mode",
        "description_en": "Shopping vocabulary — clothes, sizes, prices, and fashion expressions in French.",
        "description_bn": "কেনাকাটার শব্দভান্ডার — ফরাসিতে পোশাক, মাপ, দাম এবং ফ্যাশনের প্রকাশভঙ্গি।",
        "vocabulary_categories": ["shopping", "appearance"],
        "tip_en": "Asking the price: 'C'est combien?' or 'Ça coûte combien?' France is famous for fashion — 'la mode française' is world-renowned!",
        "tip_bn": "দাম জিজ্ঞেস করতে: 'C'est combien?' বা 'Ça coûte combien?' ফ্রান্স ফ্যাশনের জন্য বিখ্যাত — 'la mode française' বিশ্বজুড়ে পরিচিত!"
    },
    {
        "id": 22, "level": "intermediate", "icon": "👥",
        "title_en": "People & Community",
        "title_bn": "মানুষ ও সমাজ",
        "title_lang": "Les Gens et la Communauté",
        "description_en": "Describing people, professions, community services and social interactions in French.",
        "description_bn": "ফরাসিতে মানুষ, পেশা, সামাজিক সেবা এবং সামাজিক মিথস্ক্রিয়া বর্ণনা করুন।",
        "vocabulary_categories": ["people", "services"],
        "tip_en": "French social life: 'faire la bise' (cheek kiss greeting) is common. 'la mairie' (town hall) and 'la préfecture' handle official services.",
        "tip_bn": "ফরাসি সামাজিক জীবন: 'faire la bise' (গালে চুমু দেওয়ার অভিবাদন) সাধারণ। 'la mairie' (পৌর সভা) এবং 'la préfecture' সরকারি সেবা পরিচালনা করে।"
    },
    {
        "id": 23, "level": "intermediate", "icon": "🍳",
        "title_en": "Food & Cooking (Advanced)",
        "title_bn": "খাবার ও রান্না (উন্নত)",
        "title_lang": "La Nourriture et la Cuisine (Avancé)",
        "description_en": "Advanced food vocabulary — cooking methods, ingredients, French cuisine and restaurant language.",
        "description_bn": "উন্নত খাদ্য শব্দভান্ডার — রান্নার পদ্ধতি, উপাদান, ফরাসি রন্ধনশৈলী এবং রেস্তোরাঁর ভাষা।",
        "vocabulary_categories": ["food_advanced"],
        "tip_en": "Ordering in a French restaurant: 'Je voudrais...' (I would like...). The 'menu' (fixed-price meal) is better value than ordering 'à la carte'.",
        "tip_bn": "ফরাসি রেস্তোরাঁয় অর্ডার দেওয়া: 'Je voudrais...' (আমি চাই...)। 'à la carte' থেকে 'menu' (নির্ধারিত মূল্যের খাবার) বেশি সাশ্রয়ী।"
    },
    {
        "id": 24, "level": "intermediate", "icon": "✈️",
        "title_en": "Travel & Transport (Advanced)",
        "title_bn": "ভ্রমণ ও যানবাহন (উন্নত)",
        "title_lang": "Voyages et Transports (Avancé)",
        "description_en": "Advanced travel vocabulary — airports, trains, accommodation and navigating France.",
        "description_bn": "উন্নত ভ্রমণ শব্দভান্ডার — বিমানবন্দর, ট্রেন, আবাসন এবং ফ্রান্সে ঘুরে বেড়ানো।",
        "vocabulary_categories": ["transport_advanced"],
        "tip_en": "France has excellent trains! 'le TGV' (Train à Grande Vitesse) connects cities at 300km/h. Book on 'SNCF Connect' app for best prices.",
        "tip_bn": "ফ্রান্সে চমৎকার ট্রেন সেবা! 'le TGV' (Train à Grande Vitesse) শহরগুলি ৩০০ কিমি/ঘণ্টায় সংযুক্ত করে। সেরা দামের জন্য 'SNCF Connect' অ্যাপে বুক করুন।"
    }
]


NEW_SPANISH = [
    {
        "id": 16, "level": "intermediate", "icon": "🏥",
        "title_en": "Health & Medical",
        "title_bn": "স্বাস্থ্য ও চিকিৎসা",
        "title_lang": "Salud y Medicina",
        "description_en": "Essential vocabulary for doctors, pharmacies, symptoms, and healthcare in Spain.",
        "description_bn": "স্পেনে ডাক্তার, ফার্মেসি, উপসর্গ এবং স্বাস্থ্যসেবার জন্য প্রয়োজনীয় শব্দভান্ডার।",
        "vocabulary_categories": ["health"],
        "tip_en": "In Spain, say 'Me duele la cabeza' (My head hurts). Spain has excellent free healthcare — go to the 'centro de salud' (health centre) for non-emergencies.",
        "tip_bn": "স্পেনে বলুন 'Me duele la cabeza' (আমার মাথা ব্যথা করছে)। স্পেনে চমৎকার বিনামূল্যে স্বাস্থ্যসেবা আছে — জরুরি নয় এমন ক্ষেত্রে 'centro de salud' (স্বাস্থ্য কেন্দ্র)-এ যান।"
    },
    {
        "id": 17, "level": "intermediate", "icon": "🏠",
        "title_en": "Home & Living",
        "title_bn": "ঘর ও গৃহস্থালি",
        "title_lang": "El Hogar y la Vida Cotidiana",
        "description_en": "Furniture, rooms, household items and daily home life vocabulary in Spanish.",
        "description_bn": "স্প্যানিশে আসবাবপত্র, ঘরের কক্ষ, গৃহস্থালির জিনিস এবং দৈনন্দিন জীবনের শব্দভান্ডার।",
        "vocabulary_categories": ["home"],
        "tip_en": "In Spain, 'el piso' means apartment (flat), not floor! 'Alquilar un piso' = to rent an apartment. Very useful vocabulary for your PhD life in Spain!",
        "tip_bn": "স্পেনে 'el piso' মানে অ্যাপার্টমেন্ট (ফ্ল্যাট), মেঝে নয়! 'Alquilar un piso' = একটি অ্যাপার্টমেন্ট ভাড়া নেওয়া। স্পেনে PhD জীবনের জন্য খুব দরকারী শব্দভান্ডার!"
    },
    {
        "id": 18, "level": "intermediate", "icon": "⚽",
        "title_en": "Sports & Leisure",
        "title_bn": "খেলাধুলা ও অবসর",
        "title_lang": "Los Deportes y el Ocio",
        "description_en": "Talking about sports, hobbies, and leisure activities in Spanish.",
        "description_bn": "স্প্যানিশে খেলাধুলা, শখ এবং অবসর কার্যক্রম সম্পর্কে কথা বলুন।",
        "vocabulary_categories": ["sports"],
        "tip_en": "Football is a religion in Spain! 'jugar al fútbol' (to play football), 'el partido' (the match), 'el equipo' (the team). Knowing this vocabulary helps you bond with Spanish people!",
        "tip_bn": "ফুটবল স্পেনে ধর্মের মতো! 'jugar al fútbol' (ফুটবল খেলা), 'el partido' (ম্যাচ), 'el equipo' (দল)। এই শব্দভান্ডার জানলে স্প্যানিশদের সাথে সম্পর্ক গড়তে সহায়তা করে!"
    },
    {
        "id": 19, "level": "intermediate", "icon": "🌿",
        "title_en": "Nature & Environment",
        "title_bn": "প্রকৃতি ও পরিবেশ",
        "title_lang": "La Naturaleza y el Medio Ambiente",
        "description_en": "Describing nature, weather, landscapes, animals, and the environment in Spanish.",
        "description_bn": "স্প্যানিশে প্রকৃতি, আবহাওয়া, ভূদৃশ্য, প্রাণী এবং পরিবেশ বর্ণনা করুন।",
        "vocabulary_categories": ["nature"],
        "tip_en": "Spanish weather: '¿Qué tiempo hace?' (What's the weather like?). 'Hace calor' (it's hot) — very relevant in Spain! 'Hace frío' (it's cold), 'Llueve' (it rains).",
        "tip_bn": "স্প্যানিশ আবহাওয়া: '¿Qué tiempo hace?' (আবহাওয়া কেমন?)। 'Hace calor' (গরম) — স্পেনে খুব প্রাসঙ্গিক! 'Hace frío' (ঠান্ডা), 'Llueve' (বৃষ্টি হচ্ছে)।"
    },
    {
        "id": 20, "level": "intermediate", "icon": "💼",
        "title_en": "Work & Career",
        "title_bn": "কাজ ও পেশা",
        "title_lang": "El Trabajo y la Carrera",
        "description_en": "Professional vocabulary — jobs, workplace, meetings, studies and academic life in Spanish.",
        "description_bn": "পেশাদার শব্দভান্ডার — স্প্যানিশে চাকরি, কর্মক্ষেত্র, সভা, পড়াশোনা ও একাডেমিক জীবন।",
        "vocabulary_categories": ["work", "study"],
        "tip_en": "'Soy investigador/a' (I am a researcher). In Spanish universities: 'el doctorado' = PhD, 'el laboratorio' = lab, 'la tesis' = thesis — your daily words!",
        "tip_bn": "'Soy investigador/a' (আমি গবেষক)। স্প্যানিশ বিশ্ববিদ্যালয়ে: 'el doctorado' = PhD, 'el laboratorio' = ল্যাব, 'la tesis' = থিসিস — আপনার প্রতিদিনের শব্দ!"
    },
    {
        "id": 21, "level": "intermediate", "icon": "🛍️",
        "title_en": "Shopping & Fashion",
        "title_bn": "কেনাকাটা ও ফ্যাশন",
        "title_lang": "Las Compras y la Moda",
        "description_en": "Shopping vocabulary — clothes, sizes, prices and fashion expressions in Spanish.",
        "description_bn": "কেনাকাটার শব্দভান্ডার — স্প্যানিশে পোশাক, মাপ, দাম এবং ফ্যাশনের প্রকাশভঙ্গি।",
        "vocabulary_categories": ["shopping", "appearance"],
        "tip_en": "Asking the price: '¿Cuánto cuesta?' or '¿Cuánto vale?' Spain has great markets — 'el mercadillo' (flea market) and 'las rebajas' (sales in January & July)!",
        "tip_bn": "দাম জিজ্ঞেস করতে: '¿Cuánto cuesta?' বা '¿Cuánto vale?' স্পেনে দারুণ বাজার আছে — 'el mercadillo' (পিস মার্কেট) এবং 'las rebajas' (জানুয়ারি ও জুলাইয়ের সেল)!"
    },
    {
        "id": 22, "level": "intermediate", "icon": "👥",
        "title_en": "People & Community",
        "title_bn": "মানুষ ও সমাজ",
        "title_lang": "Las Personas y la Comunidad",
        "description_en": "Describing people, professions, community services and social interactions in Spanish.",
        "description_bn": "স্প্যানিশে মানুষ, পেশা, সামাজিক সেবা এবং সামাজিক মিথস্ক্রিয়া বর্ণনা করুন।",
        "vocabulary_categories": ["people", "services"],
        "tip_en": "Spanish social life: 'dar un abrazo' (giving a hug) and 'dos besos' (two cheek kisses) are common greetings. 'la comunidad de vecinos' = residents' community in apartments.",
        "tip_bn": "স্প্যানিশ সামাজিক জীবন: 'dar un abrazo' (আলিঙ্গন করা) এবং 'dos besos' (দুই গালে চুমু) সাধারণ অভিবাদন। 'la comunidad de vecinos' = অ্যাপার্টমেন্টে আবাসিক সম্প্রদায়।"
    },
    {
        "id": 23, "level": "intermediate", "icon": "🍳",
        "title_en": "Food & Cooking (Advanced)",
        "title_bn": "খাবার ও রান্না (উন্নত)",
        "title_lang": "La Comida y la Cocina (Avanzado)",
        "description_en": "Advanced food vocabulary — ingredients, Spanish cuisine, tapas culture and restaurant language.",
        "description_bn": "উন্নত খাদ্য শব্দভান্ডার — উপাদান, স্প্যানিশ রন্ধনশৈলী, তাপাস সংস্কৃতি এবং রেস্তোরাঁর ভাষা।",
        "vocabulary_categories": ["food_advanced"],
        "tip_en": "'Las tapas' (small snacks with drinks) are a Spanish tradition. 'ir de tapas' = going out for tapas. 'La cuenta, por favor' = the bill, please — very important!",
        "tip_bn": "'Las tapas' (পানীয়ের সাথে ছোট নাস্তা) স্প্যানিশ ঐতিহ্য। 'ir de tapas' = তাপাস খেতে বের হওয়া। 'La cuenta, por favor' = বিল দিন, দয়া করে — খুব গুরুত্বপূর্ণ!"
    },
    {
        "id": 24, "level": "intermediate", "icon": "✈️",
        "title_en": "Travel & Transport (Advanced)",
        "title_bn": "ভ্রমণ ও যানবাহন (উন্নত)",
        "title_lang": "Viajes y Transportes (Avanzado)",
        "description_en": "Advanced travel vocabulary — airports, trains, metro, accommodation and navigating Spain.",
        "description_bn": "উন্নত ভ্রমণ শব্দভান্ডার — বিমানবন্দর, ট্রেন, মেট্রো, আবাসন এবং স্পেনে ঘুরে বেড়ানো।",
        "vocabulary_categories": ["transport_advanced"],
        "tip_en": "Spain's AVE (Alta Velocidad Española) high-speed trains are excellent! Buy tickets on Renfe.com. 'El AVE a Madrid' connects major cities. 'El metro' is the best way around cities.",
        "tip_bn": "স্পেনের AVE (Alta Velocidad Española) হাই-স্পিড ট্রেন অসাধারণ! Renfe.com-এ টিকিট কিনুন। 'El AVE a Madrid' প্রধান শহরগুলো সংযুক্ত করে। শহরে ঘোরার সেরা উপায় 'El metro'।"
    }
]


def main():
    with open(LESSONS_FILE, encoding='utf-8') as f:
        lessons = json.load(f)

    # Check which IDs already exist
    fr_existing_ids = {l['id'] for l in lessons['french']}
    es_existing_ids = {l['id'] for l in lessons['spanish']}

    fr_added = 0
    for lesson in NEW_FRENCH:
        if lesson['id'] not in fr_existing_ids:
            lessons['french'].append(lesson)
            fr_added += 1
            print(f"  [FR] Added lesson {lesson['id']}: {lesson['title_en']}")
        else:
            print(f"  [FR] Lesson {lesson['id']} already exists — skipped")

    es_added = 0
    for lesson in NEW_SPANISH:
        if lesson['id'] not in es_existing_ids:
            lessons['spanish'].append(lesson)
            es_added += 1
            print(f"  [ES] Added lesson {lesson['id']}: {lesson['title_en']}")
        else:
            print(f"  [ES] Lesson {lesson['id']} already exists — skipped")

    with open(LESSONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(lessons, f, ensure_ascii=False, indent=2)

    print(f"\n  French  : {fr_added} lessons added  ({len(lessons['french'])} total)")
    print(f"  Spanish : {es_added} lessons added  ({len(lessons['spanish'])} total)")
    print(f"  Saved: {LESSONS_FILE}")


if __name__ == '__main__':
    main()
