"""Initial menu content and bot texts (EN/AR).

Business copy (services, FAQs, contact details) is placeholder content pending final text from Nexora.
Limits: button titles <= 20 chars, list row titles <= 24 chars (WhatsApp).

Revision ID: 0002
Revises: 0001
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

# (id, action_id, parent_id, kind, sort_order, en_title, en_body, ar_title, ar_body)
_NODES = [
    (1, "menu_main", None, "submenu", 0,
     "Main menu", "How can we help you today? Choose an option.",
     "القائمة الرئيسية", "كيف يمكننا مساعدتك اليوم؟ اختر أحد الخيارات."),
    (2, "menu_services", 1, "submenu", 1,
     "Our services", "Choose a service to learn more.",
     "خدماتنا", "اختر خدمة لمعرفة المزيد."),
    (3, "menu_about", 1, "info", 2,
     "About Nexora", "Nexora Consulting helps organizations plan, transform and grow through practical, "
                     "results-driven consulting.",
     "عن نكسورا", "تساعد نكسورا للاستشارات المؤسسات على التخطيط والتحول والنمو من خلال استشارات عملية "
                  "تركز على النتائج."),
    (4, "menu_contact", 1, "info", 3,
     "Contact us", "Email: info@nexora.example\nWorking hours: Sunday to Thursday, 9:00 to 17:00.",
     "تواصل معنا", "البريد الإلكتروني: info@nexora.example\nساعات العمل: من الأحد إلى الخميس، 9:00 إلى 17:00."),
    (5, "menu_faq", 1, "submenu", 4,
     "FAQs", "Choose a question.",
     "الأسئلة الشائعة", "اختر سؤالًا."),
    (6, "book_start", 1, "book", 5,
     "Book a consultation", "",
     "حجز استشارة", ""),
    (7, "handoff", 1, "handoff", 6,
     "Talk to a consultant", "",
     "التحدث مع مستشار", ""),
    (10, "svc_strategy", 2, "info", 1,
     "Business strategy", "We help you define clear goals, priorities and a roadmap to achieve them.",
     "استراتيجية الأعمال", "نساعدك على تحديد أهداف وأولويات واضحة وخارطة طريق لتحقيقها."),
    (11, "svc_digital", 2, "info", 2,
     "Digital transformation", "We help you modernize processes and systems with the right technology.",
     "التحول الرقمي", "نساعدك على تحديث العمليات والأنظمة باستخدام التقنية المناسبة."),
    (12, "svc_operations", 2, "info", 3,
     "Operational excellence", "We improve efficiency, quality and cost across your operations.",
     "التميز التشغيلي", "نحسّن الكفاءة والجودة والتكلفة في جميع عملياتك."),
    (13, "svc_hr", 2, "info", 4,
     "HR & organization", "We design organization structures, roles and HR policies that support growth.",
     "الموارد البشرية", "نصمم الهياكل التنظيمية والأدوار وسياسات الموارد البشرية التي تدعم النمو."),
    (20, "faq_cost", 5, "info", 1,
     "How much does it cost?", "Fees depend on scope. The first consultation is free of charge.",
     "كم تبلغ التكلفة؟", "تعتمد الرسوم على نطاق العمل. الاستشارة الأولى مجانية."),
    (21, "faq_duration", 5, "info", 2,
     "Project duration", "Most projects take between 4 and 12 weeks, depending on scope.",
     "مدة المشاريع", "تستغرق معظم المشاريع ما بين 4 و12 أسبوعًا حسب نطاق العمل."),
    (22, "faq_remote", 5, "info", 3,
     "Do you work remotely?", "Yes. We work on-site, remotely or in a hybrid model.",
     "هل تعملون عن بُعد؟", "نعم. نعمل في الموقع أو عن بُعد أو بنموذج هجين."),
]

# key: (en, ar)
_UI_TEXTS = {
    "welcome": ("Welcome to Nexora Consulting. Please choose a language.",
                "مرحبًا بك في نكسورا للاستشارات. يرجى اختيار اللغة."),
    "lang_option": ("English", "العربية"),
    "list_button": ("View options", "عرض الخيارات"),
    "opt_change_language": ("Language / اللغة", "Language / اللغة"),
    "hint_choose": ("Sorry, I didn't understand. Please choose one of the options.",
                    "عذرًا، لم أفهم. يرجى اختيار أحد الخيارات."),
    "book_choose_service": ("Which service would you like to book a consultation for?",
                            "ما الخدمة التي ترغب في حجز استشارة بشأنها؟"),
    "book_ask_name": ("Please enter your full name.", "يرجى إدخال اسمك الكامل."),
    "hint_name": ("Please enter a valid name (2 to 100 characters).",
                  "يرجى إدخال اسم صحيح (من 2 إلى 100 حرف)."),
    "book_ask_email": ("Please enter your email address.", "يرجى إدخال بريدك الإلكتروني."),
    "hint_email": ("Please enter a valid email address, for example name@example.com.",
                   "يرجى إدخال بريد إلكتروني صحيح، مثل name@example.com."),
    "book_ask_date": ("Please choose your preferred date.", "يرجى اختيار التاريخ المفضل."),
    "book_ask_time": ("Please choose your preferred time.", "يرجى اختيار الوقت المفضل."),
    "slot_morning": ("Morning", "صباحًا"),
    "slot_afternoon": ("Afternoon", "بعد الظهر"),
    "book_summary": ("Please confirm your consultation request:\nService: {service}\nName: {name}\n"
                     "Email: {email}\nDate: {date}\nTime: {slot}",
                     "يرجى تأكيد طلب الاستشارة:\nالخدمة: {service}\nالاسم: {name}\n"
                     "البريد الإلكتروني: {email}\nالتاريخ: {date}\nالوقت: {slot}"),
    "book_confirm": ("Confirm", "تأكيد"),
    "book_cancel": ("Cancel", "إلغاء"),
    "book_confirmed": ("Thank you! Your consultation request has been received. Reference: {reference}. "
                       "Our team will contact you to confirm the appointment.",
                       "شكرًا لك! تم استلام طلب الاستشارة. الرقم المرجعي: {reference}. "
                       "سيتواصل معك فريقنا لتأكيد الموعد."),
    "book_cancelled": ("Your booking has been cancelled.", "تم إلغاء الحجز."),
    "handoff_ack": ("A Nexora consultant will contact you shortly. Send \"menu\" at any time to return "
                    "to the main menu.",
                    "سيتواصل معك أحد مستشاري نكسورا قريبًا. أرسل \"القائمة\" في أي وقت للعودة إلى "
                    "القائمة الرئيسية."),
    "weekdays": ("Mon,Tue,Wed,Thu,Fri,Sat,Sun",
                 "الاثنين,الثلاثاء,الأربعاء,الخميس,الجمعة,السبت,الأحد"),
    "months": ("Jan,Feb,Mar,Apr,May,Jun,Jul,Aug,Sep,Oct,Nov,Dec",
               "يناير,فبراير,مارس,أبريل,مايو,يونيو,يوليو,أغسطس,سبتمبر,أكتوبر,نوفمبر,ديسمبر"),
}

NODES = [dict(id=i, action_id=a, parent_id=p, kind=k, sort_order=s, is_active=True)
         for i, a, p, k, s, *_ in _NODES]
TRANSLATIONS = [dict(node_id=n[0], lang=lang, title=title, body=body)
                for n in _NODES for lang, title, body in (("en", n[5], n[6]), ("ar", n[7], n[8]))]
UI_TEXTS = [dict(key=k, lang=lang, text=t) for k, (en, ar) in _UI_TEXTS.items() for lang, t in (("en", en), ("ar", ar))]


def upgrade() -> None:
    meta = sa.MetaData()
    nodes = sa.Table("menu_nodes", meta, autoload_with=op.get_bind())
    translations = sa.Table("menu_translations", meta, autoload_with=op.get_bind())
    ui_texts = sa.Table("ui_texts", meta, autoload_with=op.get_bind())
    op.bulk_insert(nodes, NODES)
    op.bulk_insert(translations, TRANSLATIONS)
    op.bulk_insert(ui_texts, UI_TEXTS)
    op.execute("SELECT setval('menu_nodes_id_seq', (SELECT MAX(id) FROM menu_nodes))")


def downgrade() -> None:
    op.execute("DELETE FROM ui_texts")
    op.execute("DELETE FROM menu_translations")
    op.execute("DELETE FROM menu_nodes")
