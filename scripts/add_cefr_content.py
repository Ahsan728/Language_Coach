#!/usr/bin/env python3
"""
scripts/add_cefr_content.py
============================
1. Adds 4 new vocabulary categories to data/vocabulary.json:
   nationalities, daily_activities, hobbies, emotions
   (both French and Spanish, with Bengali translations)

2. Adds cefr_level field to all existing lessons in data/lessons.json

3. Appends 4 new lessons (ids 25-28) for both languages

Usage:
    cd "d:/Software Dev/Language Coach"
    python scripts/add_cefr_content.py
"""

import json, os, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
VOCAB_FILE   = os.path.join(DATA_DIR, 'vocabulary.json')
LESSONS_FILE = os.path.join(DATA_DIR, 'lessons.json')


# ─────────────────────────────────────────────────────────────────────────────
# NEW VOCABULARY
# ─────────────────────────────────────────────────────────────────────────────

def make_entry(word, english, bengali, category, pronunciation='', example=None, example_en=None, example_bn=None):
    return {
        'word': word,
        'english': english,
        'bengali': bengali,
        'category': category,
        'pronunciation': pronunciation,
        'example': example or f'{word}.',
        'example_en': example_en or f'{english}.',
        'example_bn': example_bn or f'{bengali}।',
    }

# ── NATIONALITIES ─────────────────────────────────────────────────────────────

NATIONALITIES_ES = [
    make_entry('argentino/a', 'Argentine', 'আর্জেন্টিনীয়', 'nationalities', 'ar-hen-TEE-no',
               'Mi amigo es argentino.', 'My friend is Argentine.', 'আমার বন্ধু আর্জেন্টিনীয়।'),
    make_entry('chino/a', 'Chinese', 'চীনা', 'nationalities', 'CHEE-no',
               'Ella es china.', 'She is Chinese.', 'সে চীনা।'),
    make_entry('español/a', 'Spanish', 'স্প্যানিশ', 'nationalities', 'es-pan-YOL',
               'Soy española.', 'I am Spanish.', 'আমি স্প্যানিশ।'),
    make_entry('francés/a', 'French', 'ফরাসি', 'nationalities', 'fran-SES',
               'Él es francés.', 'He is French.', 'সে ফরাসি।'),
    make_entry('inglés/a', 'English/British', 'ইংরেজ', 'nationalities', 'ing-LES',
               'Mi profesora es inglesa.', 'My teacher is English.', 'আমার শিক্ষক ইংরেজ।'),
    make_entry('americano/a', 'American', 'আমেরিকান', 'nationalities', 'a-me-ri-KA-no',
               'Tengo un amigo americano.', 'I have an American friend.', 'আমার একজন আমেরিকান বন্ধু আছে।'),
    make_entry('bangladesí', 'Bangladeshi', 'বাংলাদেশি', 'nationalities', 'ban-gla-de-SI',
               'Soy bangladesí.', 'I am Bangladeshi.', 'আমি বাংলাদেশি।'),
    make_entry('indio/a', 'Indian', 'ভারতীয়', 'nationalities', 'IN-dyo',
               'Mi vecina es india.', 'My neighbour is Indian.', 'আমার প্রতিবেশী ভারতীয়।'),
    make_entry('alemán/a', 'German', 'জার্মান', 'nationalities', 'a-le-MAN',
               'Mi jefe es alemán.', 'My boss is German.', 'আমার বস জার্মান।'),
    make_entry('japonés/a', 'Japanese', 'জাপানি', 'nationalities', 'ha-po-NES',
               'Este coche es japonés.', 'This car is Japanese.', 'এই গাড়ি জাপানি।'),
    make_entry('coreano/a', 'Korean', 'কোরিয়ান', 'nationalities', 'ko-re-A-no',
               'Me gusta la música coreana.', 'I like Korean music.', 'আমি কোরিয়ান সংগীত পছন্দ করি।'),
    make_entry('brasileño/a', 'Brazilian', 'ব্রাজিলিয়ান', 'nationalities', 'bra-si-LEN-yo',
               'Neymar es brasileño.', 'Neymar is Brazilian.', 'নেইমার ব্রাজিলিয়ান।'),
    make_entry('mexicano/a', 'Mexican', 'মেক্সিকান', 'nationalities', 'me-hi-KA-no',
               'La cocina mexicana es deliciosa.', 'Mexican cuisine is delicious.', 'মেক্সিকান রান্না সুস্বাদু।'),
    make_entry('portugués/a', 'Portuguese', 'পর্তুগিজ', 'nationalities', 'por-tu-GES',
               'El fado es música portuguesa.', 'Fado is Portuguese music.', 'ফাদো পর্তুগিজ সংগীত।'),
    make_entry('ruso/a', 'Russian', 'রাশিয়ান', 'nationalities', 'ROO-so',
               'Ella habla ruso.', 'She speaks Russian.', 'সে রাশিয়ান বলে।'),
    make_entry('australiano/a', 'Australian', 'অস্ট্রেলিয়ান', 'nationalities', 'aus-tra-LYA-no',
               'Mi compañero es australiano.', 'My colleague is Australian.', 'আমার সহকর্মী অস্ট্রেলিয়ান।'),
    make_entry('marroquí', 'Moroccan', 'মরোক্কান', 'nationalities', 'ma-ro-KI',
               'La arquitectura marroquí es preciosa.', 'Moroccan architecture is beautiful.', 'মরোক্কান স্থাপত্য সুন্দর।'),
    make_entry('italiano/a', 'Italian', 'ইতালিয়ান', 'nationalities', 'i-ta-LYA-no',
               'La pizza italiana es la mejor.', 'Italian pizza is the best.', 'ইতালিয়ান পিজ্জা সেরা।'),
    make_entry('tailandés/a', 'Thai', 'থাই', 'nationalities', 'tai-lan-DES',
               'La comida tailandesa es picante.', 'Thai food is spicy.', 'থাই খাবার ঝাল।'),
    make_entry('pakistaní', 'Pakistani', 'পাকিস্তানি', 'nationalities', 'pa-kis-ta-NI',
               'Mi amigo pakistaní habla urdu.', 'My Pakistani friend speaks Urdu.', 'আমার পাকিস্তানি বন্ধু উর্দু বলে।'),
]

NATIONALITIES_FR = [
    make_entry('argentin(e)', 'Argentine', 'আর্জেন্টিনীয়', 'nationalities', 'ar-zhon-TAN',
               'Mon ami est argentin.', 'My friend is Argentine.', 'আমার বন্ধু আর্জেন্টিনীয়।'),
    make_entry('chinois(e)', 'Chinese', 'চীনা', 'nationalities', 'shi-NWAH',
               'Elle est chinoise.', 'She is Chinese.', 'সে চীনা।'),
    make_entry('espagnol(e)', 'Spanish', 'স্প্যানিশ', 'nationalities', 'es-pan-YOL',
               'Il est espagnol.', 'He is Spanish.', 'সে স্প্যানিশ।'),
    make_entry('français(e)', 'French', 'ফরাসি', 'nationalities', 'frahn-SEH',
               'Je suis française.', 'I am French.', 'আমি ফরাসি।'),
    make_entry('anglais(e)', 'English/British', 'ইংরেজ', 'nationalities', 'ahn-GLEH',
               'Mon professeur est anglais.', 'My teacher is English.', 'আমার শিক্ষক ইংরেজ।'),
    make_entry('américain(e)', 'American', 'আমেরিকান', 'nationalities', 'a-meh-ri-KAN',
               "J'ai un ami américain.", 'I have an American friend.', 'আমার একজন আমেরিকান বন্ধু আছে।'),
    make_entry('bangladais(e)', 'Bangladeshi', 'বাংলাদেশি', 'nationalities', 'ban-gla-DEH',
               'Je suis bangladais(e).', 'I am Bangladeshi.', 'আমি বাংলাদেশি।'),
    make_entry('indien(ne)', 'Indian', 'ভারতীয়', 'nationalities', 'an-DYAN',
               'Ma voisine est indienne.', 'My neighbour is Indian.', 'আমার প্রতিবেশী ভারতীয়।'),
    make_entry('allemand(e)', 'German', 'জার্মান', 'nationalities', 'al-MAHN',
               'Mon chef est allemand.', 'My boss is German.', 'আমার বস জার্মান।'),
    make_entry('japonais(e)', 'Japanese', 'জাপানি', 'nationalities', 'zha-po-NEH',
               'Cette voiture est japonaise.', 'This car is Japanese.', 'এই গাড়ি জাপানি।'),
    make_entry('coréen(ne)', 'Korean', 'কোরিয়ান', 'nationalities', 'ko-reh-AN',
               "J'aime la musique coréenne.", 'I like Korean music.', 'আমি কোরিয়ান সংগীত পছন্দ করি।'),
    make_entry('brésilien(ne)', 'Brazilian', 'ব্রাজিলিয়ান', 'nationalities', 'breh-zi-LYAN',
               'Neymar est brésilien.', 'Neymar is Brazilian.', 'নেইমার ব্রাজিলিয়ান।'),
    make_entry('mexicain(e)', 'Mexican', 'মেক্সিকান', 'nationalities', 'mek-si-KAN',
               'La cuisine mexicaine est délicieuse.', 'Mexican cuisine is delicious.', 'মেক্সিকান রান্না সুস্বাদু।'),
    make_entry('portugais(e)', 'Portuguese', 'পর্তুগিজ', 'nationalities', 'por-tu-GEH',
               'Le fado est de la musique portugaise.', 'Fado is Portuguese music.', 'ফাদো পর্তুগিজ সংগীত।'),
    make_entry('russe', 'Russian', 'রাশিয়ান', 'nationalities', 'ROOS',
               'Elle parle russe.', 'She speaks Russian.', 'সে রাশিয়ান বলে।'),
    make_entry('australien(ne)', 'Australian', 'অস্ট্রেলিয়ান', 'nationalities', 'os-tra-LYAN',
               'Mon collègue est australien.', 'My colleague is Australian.', 'আমার সহকর্মী অস্ট্রেলিয়ান।'),
    make_entry('marocain(e)', 'Moroccan', 'মরোক্কান', 'nationalities', 'ma-ro-KAN',
               "L'architecture marocaine est magnifique.", 'Moroccan architecture is magnificent.', 'মরোক্কান স্থাপত্য দুর্দান্ত।'),
    make_entry('italien(ne)', 'Italian', 'ইতালিয়ান', 'nationalities', 'i-ta-LYAN',
               'La pizza italienne est la meilleure.', 'Italian pizza is the best.', 'ইতালিয়ান পিজ্জা সেরা।'),
    make_entry('thaïlandais(e)', 'Thai', 'থাই', 'nationalities', 'ta-i-lahn-DEH',
               'La cuisine thaïlandaise est épicée.', 'Thai food is spicy.', 'থাই খাবার ঝাল।'),
    make_entry('pakistanais(e)', 'Pakistani', 'পাকিস্তানি', 'nationalities', 'pa-kis-ta-NEH',
               'Mon ami pakistanais parle ourdou.', 'My Pakistani friend speaks Urdu.', 'আমার পাকিস্তানি বন্ধু উর্দু বলে।'),
]

# ── DAILY ACTIVITIES ──────────────────────────────────────────────────────────

DAILY_ACTIVITIES_ES = [
    make_entry('ver la tele', 'watch TV', 'টিভি দেখা', 'daily_activities', 'ver la TE-le',
               'Por las noches veo la tele.', 'I watch TV in the evenings.', 'রাতে আমি টিভি দেখি।'),
    make_entry('escuchar música', 'listen to music', 'সংগীত শোনা', 'daily_activities', 'es-ku-CHAR MOO-si-ka',
               'Me relajo escuchando música.', 'I relax listening to music.', 'আমি সংগীত শুনে বিশ্রাম নিই।'),
    make_entry('trabajar', 'work', 'কাজ করা', 'daily_activities', 'tra-ba-HAR',
               'Trabajo desde casa los lunes.', 'I work from home on Mondays.', 'সোমবার আমি বাসা থেকে কাজ করি।'),
    make_entry('tomar un café', 'have a coffee', 'কফি পান করা', 'daily_activities', 'to-MAR un ka-FE',
               'Siempre tomo un café por la mañana.', 'I always have a coffee in the morning.', 'সকালে আমি সবসময় কফি পান করি।'),
    make_entry('ir a un restaurante', 'go to a restaurant', 'রেস্তোরাঁয় যাওয়া', 'daily_activities', 'ir a un res-tau-RAN-te',
               'Los viernes vamos a un restaurante.', 'On Fridays we go to a restaurant.', 'শুক্রবার আমরা রেস্তোরাঁয় যাই।'),
    make_entry('ir al supermercado', 'go to the supermarket', 'সুপারমার্কেটে যাওয়া', 'daily_activities', 'ir al su-per-mer-KA-do',
               'Voy al supermercado los sábados.', 'I go to the supermarket on Saturdays.', 'শনিবার আমি সুপারমার্কেটে যাই।'),
    make_entry('leer un libro', 'read a book', 'বই পড়া', 'daily_activities', 'le-ER un LEE-bro',
               'Leo un libro antes de dormir.', 'I read a book before sleeping.', 'ঘুমানোর আগে আমি বই পড়ি।'),
    make_entry('ir de compras', 'go shopping', 'কেনাকাটা করা', 'daily_activities', 'ir de KOM-pras',
               'Me gusta ir de compras el domingo.', 'I like going shopping on Sunday.', 'রবিবার কেনাকাটা করতে আমার ভালো লাগে।'),
    make_entry('cocinar', 'cook', 'রান্না করা', 'daily_activities', 'ko-si-NAR',
               'Me encanta cocinar platos nuevos.', 'I love cooking new dishes.', 'নতুন খাবার রান্না করতে আমার খুব ভালো লাগে।'),
    make_entry('pasear', 'go for a walk', 'হাঁটতে যাওয়া', 'daily_activities', 'pa-se-AR',
               'Paseo por el parque cada mañana.', 'I walk in the park every morning.', 'প্রতি সকালে আমি পার্কে হাঁটি।'),
    make_entry('hacer yoga', 'do yoga', 'যোগব্যায়াম করা', 'daily_activities', 'a-SER YO-ga',
               'Hago yoga tres veces a la semana.', 'I do yoga three times a week.', 'সপ্তাহে তিনবার আমি যোগব্যায়াম করি।'),
    make_entry('correr', 'run / jog', 'দৌড়ানো', 'daily_activities', 'ko-RER',
               'Corro 5 km cada mañana.', 'I run 5 km every morning.', 'প্রতি সকালে আমি ৫ কিমি দৌড়াই।'),
    make_entry('nadar', 'swim', 'সাঁতার কাটা', 'daily_activities', 'na-DAR',
               'Nado en la piscina los martes.', 'I swim in the pool on Tuesdays.', 'মঙ্গলবার আমি সুইমিং পুলে সাঁতার কাটি।'),
    make_entry('bailar', 'dance', 'নাচা', 'daily_activities', 'bai-LAR',
               'Bailo salsa los fines de semana.', 'I dance salsa on weekends.', 'সপ্তাহান্তে আমি সালসা নাচি।'),
    make_entry('hacer senderismo', 'go hiking', 'হাইকিং করা', 'daily_activities', 'a-SER sen-de-RIS-mo',
               'Hacemos senderismo en la montaña.', 'We go hiking in the mountains.', 'আমরা পাহাড়ে হাইকিং করি।'),
    make_entry('visitar a la familia', 'visit family', 'পরিবার দেখতে যাওয়া', 'daily_activities', 'vi-si-TAR a la fa-MI-lya',
               'Visito a mi familia los domingos.', 'I visit my family on Sundays.', 'রবিবার আমি পরিবার দেখতে যাই।'),
    make_entry('lavar la ropa', 'do the laundry', 'কাপড় ধোওয়া', 'daily_activities', 'la-BAR la RO-pa',
               'Lavo la ropa los miércoles.', 'I do laundry on Wednesdays.', 'বুধবার আমি কাপড় ধুই।'),
    make_entry('ir al cine', 'go to the cinema', 'সিনেমায় যাওয়া', 'daily_activities', 'ir al SI-ne',
               'Voy al cine una vez al mes.', 'I go to the cinema once a month.', 'মাসে একবার আমি সিনেমায় যাই।'),
    make_entry('levantarse', 'get up', 'উঠা', 'daily_activities', 'le-van-TAR-se',
               'Me levanto a las siete.', 'I get up at seven.', 'আমি সাতটায় ওঠি।'),
    make_entry('ducharse', 'take a shower', 'গোসল করা', 'daily_activities', 'du-CHAR-se',
               'Me ducho por la mañana.', 'I take a shower in the morning.', 'সকালে আমি গোসল করি।'),
]

DAILY_ACTIVITIES_FR = [
    make_entry('regarder la télé', 'watch TV', 'টিভি দেখা', 'daily_activities', 'ruh-gar-DEH la teh-LEH',
               'Je regarde la télé le soir.', 'I watch TV in the evening.', 'সন্ধ্যায় আমি টিভি দেখি।'),
    make_entry('écouter de la musique', 'listen to music', 'সংগীত শোনা', 'daily_activities', 'eh-koo-TEH duh la moo-ZEEK',
               "J'écoute de la musique pour me détendre.", 'I listen to music to relax.', 'আমি বিশ্রামের জন্য সংগীত শুনি।'),
    make_entry('travailler', 'work', 'কাজ করা', 'daily_activities', 'tra-va-YEH',
               'Je travaille de chez moi le lundi.', 'I work from home on Mondays.', 'সোমবার আমি বাসা থেকে কাজ করি।'),
    make_entry('prendre un café', 'have a coffee', 'কফি পান করা', 'daily_activities', 'prahn-druh un ka-FEH',
               'Je prends un café chaque matin.', 'I have a coffee every morning.', 'প্রতি সকালে আমি কফি পান করি।'),
    make_entry('aller au restaurant', 'go to a restaurant', 'রেস্তোরাঁয় যাওয়া', 'daily_activities', 'a-LEH oh res-toh-RAHN',
               'On va au restaurant le vendredi.', 'We go to the restaurant on Friday.', 'শুক্রবার আমরা রেস্তোরাঁয় যাই।'),
    make_entry('faire les courses', 'do the shopping', 'কেনাকাটা করা', 'daily_activities', 'fair leh KOORS',
               'Je fais les courses le samedi.', 'I do the shopping on Saturday.', 'শনিবার আমি কেনাকাটা করি।'),
    make_entry('lire un livre', 'read a book', 'বই পড়া', 'daily_activities', 'leer un LEE-vruh',
               'Je lis un livre avant de dormir.', 'I read a book before sleeping.', 'ঘুমানোর আগে আমি বই পড়ি।'),
    make_entry('cuisiner', 'cook', 'রান্না করা', 'daily_activities', 'kwee-zi-NEH',
               "J'adore cuisiner de nouveaux plats.", 'I love cooking new dishes.', 'নতুন খাবার রান্না করতে আমার খুব ভালো লাগে।'),
    make_entry('se promener', 'go for a walk', 'হাঁটতে যাওয়া', 'daily_activities', 'suh prom-NEH',
               'Je me promène dans le parc chaque matin.', 'I walk in the park every morning.', 'প্রতি সকালে আমি পার্কে হাঁটি।'),
    make_entry('faire du yoga', 'do yoga', 'যোগব্যায়াম করা', 'daily_activities', 'fair doo YO-ga',
               'Je fais du yoga trois fois par semaine.', 'I do yoga three times a week.', 'সপ্তাহে তিনবার আমি যোগব্যায়াম করি।'),
    make_entry('courir', 'run / jog', 'দৌড়ানো', 'daily_activities', 'koo-REER',
               'Je cours 5 km chaque matin.', 'I run 5 km every morning.', 'প্রতি সকালে আমি ৫ কিমি দৌড়াই।'),
    make_entry('nager', 'swim', 'সাঁতার কাটা', 'daily_activities', 'na-ZHEH',
               'Je nage à la piscine le mardi.', 'I swim in the pool on Tuesdays.', 'মঙ্গলবার আমি সুইমিং পুলে সাঁতার কাটি।'),
    make_entry('danser', 'dance', 'নাচা', 'daily_activities', 'dahn-SEH',
               'Je danse la salsa le week-end.', 'I dance salsa on weekends.', 'সপ্তাহান্তে আমি সালসা নাচি।'),
    make_entry('faire de la randonnée', 'go hiking', 'হাইকিং করা', 'daily_activities', 'fair duh la rahn-do-NEH',
               'Nous faisons de la randonnée en montagne.', 'We go hiking in the mountains.', 'আমরা পাহাড়ে হাইকিং করি।'),
    make_entry('rendre visite à la famille', 'visit family', 'পরিবার দেখতে যাওয়া', 'daily_activities', 'rahn-druh vee-ZEET',
               'Je rends visite à ma famille le dimanche.', 'I visit my family on Sundays.', 'রবিবার আমি পরিবার দেখতে যাই।'),
    make_entry('faire la lessive', 'do the laundry', 'কাপড় ধোওয়া', 'daily_activities', 'fair la le-SEEV',
               'Je fais la lessive le mercredi.', 'I do the laundry on Wednesdays.', 'বুধবার আমি কাপড় ধুই।'),
    make_entry('aller au cinéma', 'go to the cinema', 'সিনেমায় যাওয়া', 'daily_activities', 'a-LEH oh see-neh-MA',
               'Je vais au cinéma une fois par mois.', 'I go to the cinema once a month.', 'মাসে একবার আমি সিনেমায় যাই।'),
    make_entry('se lever', 'get up', 'উঠা', 'daily_activities', 'suh luh-VEH',
               'Je me lève à sept heures.', 'I get up at seven.', 'আমি সাতটায় ওঠি।'),
    make_entry('se doucher', 'take a shower', 'গোসল করা', 'daily_activities', 'suh doo-SHEH',
               'Je me douche le matin.', 'I take a shower in the morning.', 'সকালে আমি গোসল করি।'),
    make_entry('prendre le petit-déjeuner', 'have breakfast', 'নাস্তা করা', 'daily_activities', 'prahn-druh luh puh-tee deh-zhuh-NEH',
               'Je prends le petit-déjeuner à huit heures.', 'I have breakfast at eight.', 'আমি আটটায় নাস্তা করি।'),
]

# ── HOBBIES ───────────────────────────────────────────────────────────────────

HOBBIES_ES = [
    make_entry('esquiar', 'skiing', 'স্কি করা', 'hobbies', 'es-KI-ar',
               'Me encanta esquiar en invierno.', 'I love skiing in winter.', 'শীতকালে স্কি করতে আমার খুব ভালো লাগে।'),
    make_entry('hacer snowboard', 'snowboarding', 'স্নোবোর্ড করা', 'hobbies', 'a-SER SNOW-bord',
               'Mi hermano hace snowboard.', 'My brother does snowboarding.', 'আমার ভাই স্নোবোর্ড করে।'),
    make_entry('ir al gimnasio', 'go to the gym', 'জিমে যাওয়া', 'hobbies', 'ir al him-NA-syo',
               'Voy al gimnasio cuatro veces a la semana.', 'I go to the gym four times a week.', 'সপ্তাহে চারবার আমি জিমে যাই।'),
    make_entry('visitar museos', 'visit museums', 'জাদুঘর পরিদর্শন করা', 'hobbies', 'vi-si-TAR mu-SE-os',
               'Me gusta visitar museos de arte.', 'I like visiting art museums.', 'আমি শিল্প জাদুঘর পরিদর্শন করতে পছন্দ করি।'),
    make_entry('la música', 'music', 'সংগীত', 'hobbies', 'la MOO-si-ka',
               'La música es mi pasión.', 'Music is my passion.', 'সংগীত আমার আবেগ।'),
    make_entry('el senderismo', 'hiking', 'হাইকিং', 'hobbies', 'el sen-de-RIS-mo',
               'El senderismo es perfecto para desconectar.', 'Hiking is perfect for disconnecting.', 'হাইকিং বিশ্রামের জন্য আদর্শ।'),
    make_entry('la fotografía', 'photography', 'ফটোগ্রাফি', 'hobbies', 'la fo-to-gra-FI-a',
               'La fotografía es mi hobby favorito.', 'Photography is my favourite hobby.', 'ফটোগ্রাফি আমার প্রিয় শখ।'),
    make_entry('el dibujo', 'drawing', 'আঁকা', 'hobbies', 'el di-BOO-ho',
               'De niño me encantaba el dibujo.', 'As a child I loved drawing.', 'ছোটবেলায় আমি আঁকতে ভালোবাসতাম।'),
    make_entry('la lectura', 'reading', 'পড়া', 'hobbies', 'la lek-TOO-ra',
               'La lectura es esencial para mí.', 'Reading is essential for me.', 'পড়া আমার জন্য অপরিহার্য।'),
    make_entry('el ajedrez', 'chess', 'দাবা', 'hobbies', 'el a-he-DRES',
               'Juego al ajedrez en línea.', 'I play chess online.', 'আমি অনলাইনে দাবা খেলি।'),
    make_entry('viajar', 'travel', 'ভ্রমণ করা', 'hobbies', 'bya-HAR',
               'Viajar es mi mayor pasión.', 'Travelling is my greatest passion.', 'ভ্রমণ আমার সবচেয়ে বড় আবেগ।'),
    make_entry('tocar la guitarra', 'play guitar', 'গিটার বাজানো', 'hobbies', 'to-KAR la gi-TA-rra',
               'Toco la guitarra desde los diez años.', 'I have played guitar since I was ten.', 'দশ বছর বয়স থেকে আমি গিটার বাজাই।'),
    make_entry('ver películas', 'watch films', 'সিনেমা দেখা', 'hobbies', 'ver pe-LI-ku-las',
               'Los domingos veo películas en casa.', 'On Sundays I watch films at home.', 'রবিবার আমি বাসায় সিনেমা দেখি।'),
    make_entry('jugar videojuegos', 'play video games', 'ভিডিও গেম খেলা', 'hobbies', 'hu-GAR vi-de-o-HWE-gos',
               'Mi hijo juega videojuegos cada tarde.', 'My son plays video games every afternoon.', 'আমার ছেলে প্রতি বিকেলে ভিডিও গেম খেলে।'),
    make_entry('la pintura', 'painting', 'চিত্রকলা', 'hobbies', 'la pin-TOO-ra',
               'La pintura me ayuda a relajarme.', 'Painting helps me relax.', 'চিত্রকলা আমাকে শিথিল হতে সাহায্য করে।'),
    make_entry('el teatro', 'theatre', 'থিয়েটার', 'hobbies', 'el te-A-tro',
               'Voy al teatro una vez al mes.', 'I go to the theatre once a month.', 'মাসে একবার আমি থিয়েটারে যাই।'),
    make_entry('la jardinería', 'gardening', 'বাগান করা', 'hobbies', 'la har-di-ne-RI-a',
               'La jardinería es muy relajante.', 'Gardening is very relaxing.', 'বাগান করা খুব শান্তিদায়ক।'),
    make_entry('hacer voluntariado', 'volunteer / volunteering', 'স্বেচ্ছাসেবী কাজ', 'hobbies', 'a-SER vo-lun-ta-RYA-do',
               'Hago voluntariado los fines de semana.', 'I volunteer on weekends.', 'সপ্তাহান্তে আমি স্বেচ্ছাসেবী কাজ করি।'),
]

HOBBIES_FR = [
    make_entry('faire du ski', 'skiing', 'স্কি করা', 'hobbies', 'fair doo SKEE',
               "J'adore faire du ski en hiver.", 'I love skiing in winter.', 'শীতকালে স্কি করতে আমার খুব ভালো লাগে।'),
    make_entry('faire du snowboard', 'snowboarding', 'স্নোবোর্ড করা', 'hobbies', 'fair doo SNOW-bord',
               'Mon frère fait du snowboard.', 'My brother does snowboarding.', 'আমার ভাই স্নোবোর্ড করে।'),
    make_entry('aller à la salle de sport', 'go to the gym', 'জিমে যাওয়া', 'hobbies', 'a-LEH a la sal duh SPOR',
               "Je vais à la salle de sport quatre fois par semaine.", 'I go to the gym four times a week.', 'সপ্তাহে চারবার আমি জিমে যাই।'),
    make_entry('visiter des musées', 'visit museums', 'জাদুঘর পরিদর্শন করা', 'hobbies', 'vi-zi-TEH deh moo-ZEH',
               "J'aime visiter des musées d'art.", 'I like visiting art museums.', 'আমি শিল্প জাদুঘর পরিদর্শন করতে পছন্দ করি।'),
    make_entry('la musique', 'music', 'সংগীত', 'hobbies', 'la moo-ZEEK',
               'La musique est ma passion.', 'Music is my passion.', 'সংগীত আমার আবেগ।'),
    make_entry('la randonnée', 'hiking', 'হাইকিং', 'hobbies', 'la rahn-do-NEH',
               'La randonnée est parfaite pour se déconnecter.', 'Hiking is perfect for disconnecting.', 'হাইকিং বিশ্রামের জন্য আদর্শ।'),
    make_entry('la photographie', 'photography', 'ফটোগ্রাফি', 'hobbies', 'la fo-to-gra-FEE',
               'La photographie est mon hobby préféré.', 'Photography is my favourite hobby.', 'ফটোগ্রাফি আমার প্রিয় শখ।'),
    make_entry('le dessin', 'drawing', 'আঁকা', 'hobbies', 'luh deh-SAN',
               "Enfant, j'adorais le dessin.", 'As a child I loved drawing.', 'ছোটবেলায় আমি আঁকতে ভালোবাসতাম।'),
    make_entry('la lecture', 'reading', 'পড়া', 'hobbies', 'la lek-TOOR',
               'La lecture est essentielle pour moi.', 'Reading is essential for me.', 'পড়া আমার জন্য অপরিহার্য।'),
    make_entry('les échecs', 'chess', 'দাবা', 'hobbies', 'leh zeh-SHEK',
               'Je joue aux échecs en ligne.', 'I play chess online.', 'আমি অনলাইনে দাবা খেলি।'),
    make_entry('voyager', 'travel', 'ভ্রমণ করা', 'hobbies', 'vwa-ya-ZHEH',
               'Voyager est ma plus grande passion.', 'Travelling is my greatest passion.', 'ভ্রমণ আমার সবচেয়ে বড় আবেগ।'),
    make_entry('jouer de la guitare', 'play guitar', 'গিটার বাজানো', 'hobbies', 'zhoo-EH duh la gee-TAR',
               'Je joue de la guitare depuis mes dix ans.', 'I have played guitar since I was ten.', 'দশ বছর বয়স থেকে আমি গিটার বাজাই।'),
    make_entry('regarder des films', 'watch films', 'সিনেমা দেখা', 'hobbies', 'ruh-gar-DEH deh FEELM',
               'Le dimanche, je regarde des films chez moi.', 'On Sundays I watch films at home.', 'রবিবার আমি বাসায় সিনেমা দেখি।'),
    make_entry('jouer aux jeux vidéo', 'play video games', 'ভিডিও গেম খেলা', 'hobbies', 'zhoo-EH oh zhuh vi-deh-OH',
               'Mon fils joue aux jeux vidéo chaque après-midi.', 'My son plays video games every afternoon.', 'আমার ছেলে প্রতি বিকেলে ভিডিও গেম খেলে।'),
    make_entry('la peinture', 'painting', 'চিত্রকলা', 'hobbies', 'la pan-TOOR',
               'La peinture m\'aide à me détendre.', 'Painting helps me relax.', 'চিত্রকলা আমাকে শিথিল হতে সাহায্য করে।'),
    make_entry('le théâtre', 'theatre', 'থিয়েটার', 'hobbies', 'luh teh-AH-truh',
               'Je vais au théâtre une fois par mois.', 'I go to the theatre once a month.', 'মাসে একবার আমি থিয়েটারে যাই।'),
    make_entry('le jardinage', 'gardening', 'বাগান করা', 'hobbies', 'luh zhar-di-NAHZH',
               'Le jardinage est très relaxant.', 'Gardening is very relaxing.', 'বাগান করা খুব শান্তিদায়ক।'),
    make_entry('faire du bénévolat', 'volunteer / volunteering', 'স্বেচ্ছাসেবী কাজ', 'hobbies', 'fair doo beh-neh-vo-LA',
               'Je fais du bénévolat le week-end.', 'I volunteer on weekends.', 'সপ্তাহান্তে আমি স্বেচ্ছাসেবী কাজ করি।'),
]

# ── EMOTIONS ──────────────────────────────────────────────────────────────────

EMOTIONS_ES = [
    make_entry('me gusta', 'I like', 'আমার পছন্দ', 'emotions', 'me GOOS-ta',
               'Me gusta el café con leche.', 'I like coffee with milk.', 'দুধ কফি আমার পছন্দ।'),
    make_entry('me encanta', 'I love / I adore', 'আমি ভালোবাসি', 'emotions', 'me en-KAN-ta',
               'Me encanta viajar por España.', 'I love travelling around Spain.', 'স্পেনে ভ্রমণ করতে আমি ভালোবাসি।'),
    make_entry('me fascina', 'it fascinates me', 'আমাকে মুগ্ধ করে', 'emotions', 'me fas-SI-na',
               'Me fascina la cultura japonesa.', 'Japanese culture fascinates me.', 'জাপানি সংস্কৃতি আমাকে মুগ্ধ করে।'),
    make_entry('me sorprende', 'it surprises me', 'আমাকে অবাক করে', 'emotions', 'me sor-PREN-de',
               'Me sorprende su inteligencia.', 'Their intelligence surprises me.', 'তাদের বুদ্ধিমত্তা আমাকে অবাক করে।'),
    make_entry('me entristece', 'it saddens me', 'আমাকে দুঃখী করে', 'emotions', 'me en-tris-TE-se',
               'Me entristece ver tanta pobreza.', 'It saddens me to see so much poverty.', 'এত দারিদ্র্য দেখে আমার মন খারাপ হয়।'),
    make_entry('me da rabia', 'it makes me angry', 'আমাকে রাগান্বিত করে', 'emotions', 'me da RA-bya',
               'Me da rabia la injusticia.', 'Injustice makes me angry.', 'অবিচার আমাকে রাগান্বিত করে।'),
    make_entry('me alegra', 'it makes me happy', 'আমাকে খুশি করে', 'emotions', 'me a-LE-gra',
               'Me alegra ver a mis amigos.', 'Seeing my friends makes me happy.', 'বন্ধুদের দেখলে আমি খুশি হই।'),
    make_entry('me preocupa', 'it worries me', 'আমাকে চিন্তিত করে', 'emotions', 'me pre-o-KOO-pa',
               'Me preocupa el cambio climático.', 'Climate change worries me.', 'জলবায়ু পরিবর্তন আমাকে চিন্তিত করে।'),
    make_entry('me aburre', 'it bores me', 'আমাকে বিরক্ত করে', 'emotions', 'me a-BOO-rre',
               'Me aburre la burocracia.', 'Bureaucracy bores me.', 'আমলাতন্ত্র আমাকে বিরক্ত করে।'),
    make_entry('me molesta', 'it bothers me', 'আমাকে বিরক্ত করে', 'emotions', 'me mo-LES-ta',
               'Me molesta el ruido por la noche.', 'Noise at night bothers me.', 'রাতে শব্দ আমাকে বিরক্ত করে।'),
    make_entry('estar contento/a', 'to be happy', 'খুশি থাকা', 'emotions', 'es-TAR kon-TEN-to',
               'Estoy contento con mis resultados.', 'I am happy with my results.', 'আমার ফলাফলে আমি খুশি।'),
    make_entry('estar triste', 'to be sad', 'দুঃখী থাকা', 'emotions', 'es-TAR TRIS-te',
               'Estoy triste porque llueve.', 'I am sad because it is raining.', 'বৃষ্টি হচ্ছে বলে আমি দুঃখী।'),
    make_entry('estar nervioso/a', 'to be nervous', 'নার্ভাস থাকা', 'emotions', 'es-TAR ner-BYO-so',
               'Estoy nervioso antes del examen.', 'I am nervous before the exam.', 'পরীক্ষার আগে আমি নার্ভাস।'),
    make_entry('estar emocionado/a', 'to be excited', 'উত্তেজিত থাকা', 'emotions', 'es-TAR e-mo-syo-NA-do',
               'Estoy emocionado por el viaje.', 'I am excited about the trip.', 'ভ্রমণ নিয়ে আমি উত্তেজিত।'),
    make_entry('estar enfadado/a', 'to be angry', 'রাগান্বিত থাকা', 'emotions', 'es-TAR en-fa-DA-do',
               'Está enfadado conmigo.', 'He/She is angry with me.', 'সে আমার উপর রাগান্বিত।'),
    make_entry('estar cansado/a', 'to be tired', 'ক্লান্ত থাকা', 'emotions', 'es-TAR kan-SA-do',
               'Estoy muy cansado después del trabajo.', 'I am very tired after work.', 'কাজের পর আমি খুব ক্লান্ত।'),
    make_entry('estar asustado/a', 'to be scared', 'ভয় পাওয়া', 'emotions', 'es-TAR a-sus-TA-do',
               'El niño está asustado de la oscuridad.', 'The child is scared of the dark.', 'শিশুটি অন্ধকারে ভয় পায়।'),
    make_entry('estar orgulloso/a', 'to be proud', 'গর্বিত থাকা', 'emotions', 'es-TAR or-gu-LYO-so',
               'Estoy muy orgulloso de ti.', 'I am very proud of you.', 'আমি তোমার জন্য খুব গর্বিত।'),
]

EMOTIONS_FR = [
    make_entry("j'aime", 'I like', 'আমার পছন্দ', 'emotions', 'ZHEM',
               "J'aime le café au lait.", 'I like coffee with milk.', 'দুধ কফি আমার পছন্দ।'),
    make_entry("j'adore", 'I love / I adore', 'আমি ভালোবাসি', 'emotions', 'zha-DOR',
               "J'adore voyager en France.", 'I love travelling in France.', 'ফ্রান্সে ভ্রমণ করতে আমি ভালোবাসি।'),
    make_entry('ça me fascine', 'it fascinates me', 'আমাকে মুগ্ধ করে', 'emotions', 'sa muh fa-SEEN',
               'La culture japonaise me fascine.', 'Japanese culture fascinates me.', 'জাপানি সংস্কৃতি আমাকে মুগ্ধ করে।'),
    make_entry('ça me surprend', 'it surprises me', 'আমাকে অবাক করে', 'emotions', 'sa muh soor-PRAHN',
               'Son intelligence me surprend.', 'Their intelligence surprises me.', 'তাদের বুদ্ধিমত্তা আমাকে অবাক করে।'),
    make_entry('ça me rend triste', 'it makes me sad', 'আমাকে দুঃখী করে', 'emotions', 'sa muh rahn TREEST',
               'Voir tant de pauvreté me rend triste.', 'Seeing so much poverty makes me sad.', 'এত দারিদ্র্য দেখে আমার মন খারাপ হয়।'),
    make_entry("ça m'énerve", 'it annoys / angers me', 'আমাকে বিরক্ত করে', 'emotions', 'sa meh-NERV',
               "L'injustice m'énerve vraiment.", 'Injustice really angers me.', 'অবিচার সত্যিই আমাকে রাগান্বিত করে।'),
    make_entry('ça me rend heureux/se', 'it makes me happy', 'আমাকে খুশি করে', 'emotions', 'sa muh rahn uh-RUH',
               'Voir mes amis me rend heureux.', 'Seeing my friends makes me happy.', 'বন্ধুদের দেখলে আমি খুশি হই।'),
    make_entry("ça m'inquiète", 'it worries me', 'আমাকে চিন্তিত করে', 'emotions', 'sa mah-KYET',
               "Le changement climatique m'inquiète.", 'Climate change worries me.', 'জলবায়ু পরিবর্তন আমাকে চিন্তিত করে।'),
    make_entry("ça m'ennuie", 'it bores me', 'আমাকে বিরক্ত করে', 'emotions', 'sa mah-NWEE',
               "La bureaucratie m'ennuie.", 'Bureaucracy bores me.', 'আমলাতন্ত্র আমাকে বিরক্ত করে।'),
    make_entry('ça me dérange', 'it bothers me', 'আমাকে বিরক্ত করে', 'emotions', 'sa muh deh-RANZH',
               'Le bruit la nuit me dérange.', 'Noise at night bothers me.', 'রাতে শব্দ আমাকে বিরক্ত করে।'),
    make_entry('être content(e)', 'to be happy', 'খুশি থাকা', 'emotions', 'etr kon-TAHN',
               'Je suis content(e) de mes résultats.', 'I am happy with my results.', 'আমার ফলাফলে আমি খুশি।'),
    make_entry('être triste', 'to be sad', 'দুঃখী থাকা', 'emotions', 'etr TREEST',
               'Je suis triste parce qu\'il pleut.', 'I am sad because it is raining.', 'বৃষ্টি হচ্ছে বলে আমি দুঃখী।'),
    make_entry('être nerveux/se', 'to be nervous', 'নার্ভাস থাকা', 'emotions', 'etr ner-VUH',
               "Je suis nerveux/se avant l'examen.", 'I am nervous before the exam.', 'পরীক্ষার আগে আমি নার্ভাস।'),
    make_entry('être enthousiaste', 'to be excited / enthusiastic', 'উত্তেজিত থাকা', 'emotions', 'etr ahn-too-zYAST',
               'Je suis enthousiaste pour le voyage.', 'I am excited about the trip.', 'ভ্রমণ নিয়ে আমি উত্তেজিত।'),
    make_entry('être en colère', 'to be angry', 'রাগান্বিত থাকা', 'emotions', 'etr ahn ko-LAIR',
               'Il/Elle est en colère contre moi.', 'He/She is angry with me.', 'সে আমার উপর রাগান্বিত।'),
    make_entry('être fatigué(e)', 'to be tired', 'ক্লান্ত থাকা', 'emotions', 'etr fa-ti-GEH',
               'Je suis très fatigué(e) après le travail.', 'I am very tired after work.', 'কাজের পর আমি খুব ক্লান্ত।'),
    make_entry('avoir peur', 'to be scared', 'ভয় পাওয়া', 'emotions', 'a-VWAR PUR',
               "L'enfant a peur du noir.", 'The child is scared of the dark.', 'শিশুটি অন্ধকারে ভয় পায়।'),
    make_entry('être fier/fière', 'to be proud', 'গর্বিত থাকা', 'emotions', 'etr FYAIR',
               'Je suis très fier/fière de toi.', 'I am very proud of you.', 'আমি তোমার জন্য খুব গর্বিত।'),
]


# ─────────────────────────────────────────────────────────────────────────────
# CEFR LESSON MAPPING
# ─────────────────────────────────────────────────────────────────────────────

CEFR_MAP = {
    1: 'A1', 2: 'A1', 3: 'A1', 4: 'A1', 5: 'A1', 6: 'A1', 7: 'A1',
    8: 'A1', 9: 'A1', 10: 'A1', 11: 'A1', 12: 'A1',
    13: 'A2', 14: 'A2', 15: 'A1',
    16: 'A2', 17: 'A2', 18: 'A2', 19: 'A2', 20: 'A2',
    21: 'A2', 22: 'A2', 23: 'B1', 24: 'A2',
    25: 'A1', 26: 'A1', 27: 'A1', 28: 'A2',
}


# ─────────────────────────────────────────────────────────────────────────────
# NEW LESSONS 25-28
# ─────────────────────────────────────────────────────────────────────────────

NEW_LESSONS_FR = [
    {
        "id": 25, "level": "A1", "cefr_level": "A1", "icon": "🌍",
        "title_en": "Nationalities & Countries",
        "title_bn": "জাতীয়তা ও দেশ",
        "title_lang": "Les Nationalités et les Pays",
        "description_en": "Say where people are from and describe nationalities in French — with gender agreement.",
        "description_bn": "ফরাসিতে মানুষ কোথা থেকে এসেছে বলুন এবং জাতীয়তা বর্ণনা করুন — লিঙ্গ মিল সহ।",
        "vocabulary_categories": ["nationalities"],
        "tip_en": "French nationalities agree with gender: français → française. NEVER capitalise them: 'je suis bangladais(e)' — lowercase always!",
        "tip_bn": "ফরাসিতে জাতীয়তা লিঙ্গের সাথে মিলে: français → française। এগুলো কখনো বড় হাতে লেখা হয় না: 'je suis bangladais(e)'।"
    },
    {
        "id": 26, "level": "A1", "cefr_level": "A1", "icon": "📅",
        "title_en": "Daily Activities & Routine",
        "title_bn": "দৈনন্দিন কার্যক্রম ও রুটিন",
        "title_lang": "Les Activités Quotidiennes",
        "description_en": "Describe your daily routine in French — morning to night, using reflexive verbs.",
        "description_bn": "ফরাসিতে আপনার দৈনন্দিন রুটিন বর্ণনা করুন — সকাল থেকে রাত পর্যন্ত, রিফ্লেক্সিভ ক্রিয়া ব্যবহার করে।",
        "vocabulary_categories": ["daily_activities"],
        "tip_en": "French daily routine uses reflexive verbs: 'Je me lève' (I get up), 'Je me douche' (I shower), 'Je me couche' (I go to bed). The 'me' changes per person!",
        "tip_bn": "ফরাসিতে রিফ্লেক্সিভ ক্রিয়া: 'Je me lève' (আমি উঠি), 'Je me douche' (আমি গোসল করি), 'Je me couche' (আমি শুতে যাই)। 'me' প্রতিটি সর্বনামের সাথে পরিবর্তন হয়!"
    },
    {
        "id": 27, "level": "A1", "cefr_level": "A1", "icon": "🎸",
        "title_en": "Hobbies & Interests",
        "title_bn": "শখ ও আগ্রহ",
        "title_lang": "Les Loisirs et les Intérêts",
        "description_en": "Talk about your hobbies, sports and interests in French.",
        "description_bn": "ফরাসিতে আপনার শখ, খেলাধুলা এবং আগ্রহ সম্পর্কে কথা বলুন।",
        "vocabulary_categories": ["hobbies"],
        "tip_en": "For sports/activities: 'Je fais du ski / de la randonnée / du vélo.' For instruments: 'Je joue de la guitare / du piano.' Use 'faire de' for most activities!",
        "tip_bn": "খেলাধুলার জন্য: 'Je fais du ski / de la randonnée / du vélo.' বাদ্যযন্ত্রের জন্য: 'Je joue de la guitare / du piano.' বেশিরভাগ কার্যক্রমে 'faire de' ব্যবহার করুন!"
    },
    {
        "id": 28, "level": "A2", "cefr_level": "A2", "icon": "💭",
        "title_en": "Emotions & Feelings",
        "title_bn": "আবেগ ও অনুভূতি",
        "title_lang": "Les Émotions et les Sentiments",
        "description_en": "Express emotions, feelings and reactions in French — from happiness to frustration.",
        "description_bn": "ফরাসিতে আবেগ, অনুভূতি এবং প্রতিক্রিয়া প্রকাশ করুন — আনন্দ থেকে হতাশা পর্যন্ত।",
        "vocabulary_categories": ["emotions"],
        "tip_en": "French feelings: 'J'aime / J'adore + infinitive'. For states: 'Je suis content(e) / triste / fatigué(e).' Adjectives agree with gender: content → contente!",
        "tip_bn": "ফরাসিতে অনুভূতি: 'J'aime / J'adore + ক্রিয়া'। অবস্থার জন্য: 'Je suis content(e) / triste / fatigué(e).' বিশেষণ লিঙ্গের সাথে মিলে: content → contente!"
    },
]

NEW_LESSONS_ES = [
    {
        "id": 25, "level": "A1", "cefr_level": "A1", "icon": "🌍",
        "title_en": "Nationalities & Countries",
        "title_bn": "জাতীয়তা ও দেশ",
        "title_lang": "Las Nacionalidades y los Países",
        "description_en": "Say where people are from and describe nationalities in Spanish — with gender agreement.",
        "description_bn": "স্প্যানিশে মানুষ কোথা থেকে এসেছে বলুন এবং জাতীয়তা বর্ণনা করুন — লিঙ্গ মিল সহ।",
        "vocabulary_categories": ["nationalities"],
        "tip_en": "Nationalities agree with gender: español → española. Most end in -o/-a. 'Soy bangladesí' — same form for M/F! Never capitalise: 'soy español', not 'Español'.",
        "tip_bn": "জাতীয়তা লিঙ্গের সাথে মিলে: español → española। বেশিরভাগ -o/-a দিয়ে শেষ হয়। 'Soy bangladesí' — নারী-পুরুষ উভয়ের জন্য একই! বড় হাতে লেখা হয় না।"
    },
    {
        "id": 26, "level": "A1", "cefr_level": "A1", "icon": "📅",
        "title_en": "Daily Activities & Routine",
        "title_bn": "দৈনন্দিন কার্যক্রম ও রুটিন",
        "title_lang": "Las Actividades Cotidianas",
        "description_en": "Describe your daily routine in Spanish — reflexive verbs, habits and everyday actions.",
        "description_bn": "স্প্যানিশে আপনার দৈনন্দিন রুটিন বর্ণনা করুন — রিফ্লেক্সিভ ক্রিয়া, অভ্যাস এবং দৈনন্দিন কার্যক্রম।",
        "vocabulary_categories": ["daily_activities"],
        "tip_en": "Use 'suelo + infinitive' for habits: 'Suelo levantarme a las 7' (I usually get up at 7). Reflexive verbs need pronouns: me levanto, te duchas, se levanta.",
        "tip_bn": "অভ্যাসের জন্য 'suelo + ক্রিয়া': 'Suelo levantarme a las 7' (আমি সাধারণত ৭টায় উঠি)। রিফ্লেক্সিভ ক্রিয়ায় সর্বনাম লাগে: me levanto, te duchas, se levanta।"
    },
    {
        "id": 27, "level": "A1", "cefr_level": "A1", "icon": "🎸",
        "title_en": "Hobbies & Interests",
        "title_bn": "শখ ও আগ্রহ",
        "title_lang": "Las Aficiones y los Intereses",
        "description_en": "Talk about your hobbies, sports and interests in Spanish.",
        "description_bn": "স্প্যানিশে আপনার শখ, খেলাধুলা এবং আগ্রহ সম্পর্কে কথা বলুন।",
        "vocabulary_categories": ["hobbies"],
        "tip_en": "For activities: 'Hago yoga / Hago senderismo / Hago snowboard.' For sports with ball: 'Juego al fútbol / al ajedrez.' For instruments: 'Toco la guitarra.'",
        "tip_bn": "কার্যক্রমের জন্য: 'Hago yoga / senderismo / snowboard.' বল খেলার জন্য: 'Juego al fútbol / al ajedrez.' বাদ্যযন্ত্রের জন্য: 'Toco la guitarra.'"
    },
    {
        "id": 28, "level": "A2", "cefr_level": "A2", "icon": "💭",
        "title_en": "Emotions & Feelings",
        "title_bn": "আবেগ ও অনুভূতি",
        "title_lang": "Las Emociones y los Sentimientos",
        "description_en": "Express emotions, feelings and reactions in Spanish — including the powerful gustar-type verbs.",
        "description_bn": "স্প্যানিশে আবেগ, অনুভূতি এবং প্রতিক্রিয়া প্রকাশ করুন — শক্তিশালী gustar-টাইপ ক্রিয়া সহ।",
        "vocabulary_categories": ["emotions"],
        "tip_en": "Gustar-type verbs flip the sentence! 'Me gusta viajar' = I like travelling (lit: travelling pleases me). Plural noun → plural verb: 'Me encantan los libros' (I love books)!",
        "tip_bn": "Gustar-টাইপ ক্রিয়া বাক্য উল্টে দেয়! 'Me gusta viajar' = আমি ভ্রমণ পছন্দ করি (অর্থাৎ: ভ্রমণ আমাকে আনন্দিত করে)। বহুবচনে: 'Me encantan los libros' (বইগুলো আমার খুব পছন্দ)!"
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def load_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)

def save_json(data, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    # ── 1. Vocabulary ────────────────────────────────────────────────────────
    print("Loading vocabulary.json …")
    vocab = load_json(VOCAB_FILE)

    new_cats = {
        'french': {
            'nationalities': NATIONALITIES_FR,
            'daily_activities': DAILY_ACTIVITIES_FR,
            'hobbies': HOBBIES_FR,
            'emotions': EMOTIONS_FR,
        },
        'spanish': {
            'nationalities': NATIONALITIES_ES,
            'daily_activities': DAILY_ACTIVITIES_ES,
            'hobbies': HOBBIES_ES,
            'emotions': EMOTIONS_ES,
        },
    }

    for lang, cats in new_cats.items():
        for cat, entries in cats.items():
            if cat in vocab[lang]:
                print(f"  [{lang}] {cat} already exists — skipping")
            else:
                vocab[lang][cat] = entries
                print(f"  [{lang}] Added {cat}: {len(entries)} entries")

    save_json(vocab, VOCAB_FILE)
    print(f"  vocabulary.json saved")

    # ── 2. Lessons ────────────────────────────────────────────────────────────
    print("\nLoading lessons.json …")
    lessons = load_json(LESSONS_FILE)

    for lang in ['french', 'spanish']:
        # Add cefr_level to existing lessons
        for lesson in lessons[lang]:
            lid = lesson['id']
            if 'cefr_level' not in lesson:
                lesson['cefr_level'] = CEFR_MAP.get(lid, 'A1')
                # Also update the 'level' field to match CEFR
                lesson['level'] = lesson['cefr_level']

        # Add new lessons 25-28 if not present
        existing_ids = {l['id'] for l in lessons[lang]}
        new_lessons = NEW_LESSONS_FR if lang == 'french' else NEW_LESSONS_ES
        for nl in new_lessons:
            if nl['id'] not in existing_ids:
                lessons[lang].append(nl)
                print(f"  [{lang}] Added lesson {nl['id']}: {nl['title_en']}")
            else:
                print(f"  [{lang}] Lesson {nl['id']} already exists — skipped")

    save_json(lessons, LESSONS_FILE)
    print(f"  lessons.json saved")

    # ── Summary ───────────────────────────────────────────────────────────────
    for lang in ['french', 'spanish']:
        total_words = sum(len(v) for v in vocab[lang].values())
        total_lessons = len(lessons[lang])
        cefr_groups = {}
        for l in lessons[lang]:
            cl = l.get('cefr_level', '?')
            cefr_groups.setdefault(cl, []).append(l['id'])
        print(f"\n  {lang.upper()}: {total_words} words, {total_lessons} lessons")
        for lvl, ids in sorted(cefr_groups.items()):
            print(f"    {lvl}: {len(ids)} lessons  {ids}")


if __name__ == '__main__':
    main()
