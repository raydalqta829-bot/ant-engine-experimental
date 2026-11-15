import json,zipfile
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A3,landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import matplotlib
ROOT=Path(__file__).parent;v=json.loads((ROOT/'VERIFICATION.json').read_text())
order=['compact_one_bedroom','family_two_bedrooms','expanded_hospitality']
titles=['A | Compact - one ground bedroom','B | Family - two ground bedrooms','C | Expanded hospitality']
arabic=['أصغر','عائلية','ضيافة أكبر']
font=Path(matplotlib.get_data_path())/'fonts'/'ttf'
for name,file in [('DV','DejaVuSans.ttf'),('DV-Bold','DejaVuSans-Bold.ttf')]:pdfmetrics.registerFont(TTFont(name,str(font/file)))
W,H=landscape(A3);doc=canvas.Canvas(str(ROOT/'GROUND_PROGRAM_COMPARISON.pdf'),pagesize=(W,H));doc.setTitle('ANT - Three ground programmes, same plot')
for floor in ['GROUND','FIRST']:
    doc.setFillColorRGB(.12,.25,.21);doc.setFont('DV-Bold',21);doc.drawString(25,H-40,'ANT | Three ground programmes - '+('ground floors' if floor=='GROUND' else 'coordinated first floors'))
    doc.setFont('DV',10);doc.drawString(25,H-62,'Same 30 x 35 m south-street plot. Same upper brief: 3 child bedrooms + master, 2 baths, family lounge and terrace.')
    width=(W-68)/3
    for i,name in enumerate(order):
        x=22+i*(width+12);s=v['cases'][name];doc.setFont('DV-Bold',11);doc.drawString(x,H-101,titles[i])
        doc.drawImage(ImageReader(str(ROOT/'cases'/name/('COORD_'+floor+'.png'))),x,245,width=width,height=H-355,preserveAspectRatio=True,anchor='c')
        rows=[('Requested ground functions',str(s['requested_ground_functions'])),('Ground bedrooms',str(s['ground_bedrooms'])),('Ground entrances',str(s['ground_entrances'])),('Ground room polygons',f"{s['ground_gross_room_polygons_m2']:.2f} m2"),('Upper room polygons',f"{s['upper_gross_room_polygons_m2']:.2f} m2"),('Programme / geometry gates','PASS - preliminary')]
        for y,(label,value) in zip([220,200,180,160,140,120],rows):doc.setFont('DV',9);doc.drawString(x,y,label);doc.setFont('DV-Bold',9);doc.drawRightString(x+width-5,y,value)
    doc.setFont('DV',8.5)
    for y,text in [(87,'Room lists and connection graphs drive CP-SAT. Prior coordinates are unlocked hints. Figures are fitted for comparison, not at a common printed scale.'),(69,'Wall-centre polygon areas are comparison metrics, not municipal building areas. Furnishing remains omitted. Strict warnings are disclosed in REPORT_AR.md.'),(51,'PRELIMINARY RESEARCH ONLY. Column alignment is checked; member capacity, roof support system, soil, reinforcement and local rules are not approved.')]:doc.drawString(25,y,text)
    doc.showPage()
doc.save()
report='''# تعميم برنامج الأرضي — ثلاث حالات مقاسة

نجحت الحالات الثلاث في بوابات البرنامج والهندسة المحددة، مع دور أول يطابق نفس البرنامج في الحالات كلها: ثلاث غرف أولاد، ورئيسية بحمامها، وحمام عائلي وصالة وتراس. الأرض ثابتة 30×35 م، والشارع جنوبي، والارتدادات المفترضة 3 م. هذه برامج اختبار اخترناها؛ لم نغيّر فيلا A2 أو الموقع المنشور أو الفرع المؤرشف.

| الحالة | الوظائف الأرضية المطلوبة | غرف النوم الأرضية | المداخل | مضلعات غرف الأرضي م² |
|---|---:|---:|---:|---:|
'''
for i,name in enumerate(order):
    s=v['cases'][name];report+=f'| {arabic[i]} | {s["requested_ground_functions"]} | {s["ground_bedrooms"]} | {s["ground_entrances"]} | {s["ground_gross_room_polygons_m2"]:.2f} |\n'
report+='''
الأصغر: مجلس رجال وخدماته، ومعيشة وطعام ومطبخ ومخزن وغرفة نوم بحمامها. العائلية تضيف غرفة ثانية وحمامًا عائليًا. الضيافة الأكبر تضم مجلسي رجال ونساء وطعام ضيوف وخدماتها ومداخل مستقلة للرجال والأسرة والنساء؛ الحد الأدنى المختار للمجلسين 45 و32 م² صافية. الوظائف لا تشمل الحركة والسلم؛ إجمالي فراغات الأرضي 11 و13 و15 على الترتيب. المساحات عند محاور الجدران وليست مساحات بلدية أو تكلفة تنفيذ. الصور في اللوحة ليست بمقياس طباعة موحد.

## ما تغير برمجيًا

أزيل شرط قائمة أسماء الغرف الإحدى عشرة من محلّل الأرضي ومدققه. ينشئ CP-SAT المتغيرات من قائمة الطلب ويقرأ الأنواع والمساحات والعروض الدنيا وروابط الوصول ومجموعات الأسرة والضيوف والمداخل. التلميحات السابقة غير مقفلة؛ لا يُعاد رسم مخزن إذا فشل البحث. الأدوار التنظيمية الأساسية للمداخل والمعيشة والسلم ما زالت مسماة. المدخل JSON منظم، ولا ندعي فهم أي برنامج من نص حر.

في العائلية وُلدت الغرفة الثانية وحمامها فعليًا. فحص الخصوصية يختبر غرفتي النوم بحسب نوع bedroom، بما فيهما المعرف الجديد bedroom_2. لا يُضاف مجلس النساء أو مدخله إلى الحالتين اللتين لا تطلبانه. تُقارن الغرف والمضلعات وشبكة الأبواب والمداخل في خرج ArchLang بالطلب، وليس ببيانات الحل وحدها.

## التنسيق بين الدورين

أُتيح للموزع العلوي استخدام ما يصل إلى أربعة أذرع متغيرة. حُفظت محاولات أثبتت أن أرضيًا ناجحًا وحده لا يضمن تركيب الأول ضمن عائلة البحث. عُدّل تماسك الغلاف، وأضيفت قاعدة تنسيق محدودة أغلقت فجوة غير مبنية في العائلية بنحو 2.52 م²، بعرض 1.80 م لاتصال علوي أوسع. لم تُحذف غرفة أو يتحرك مستطيلها الأصلي، وأُعيد فحص الأرضي والخصوصية والارتدادات. هذا إصلاح هندسي موثق بعد حل CP-SAT، وليس ادعاء حل مشترك مثالي للدورين.

أصبح اختيار مجاري الحمامين العلويين مشتركًا حتى لا ينجح أحدهما على حساب البهو السفلي. حجز المجرى 30×30 سم افتراض مكاني؛ الغلاف والميول والربط الأفقي والتفاصيل غير معتمدة. يتطابق السلم والمجاري رأسيًا بقواعد keep stacked، وكل حجز عمود مستمر في الأعلى يطابق حجزه السفلي في خرج المترجم.

كشف فحص سماكة الجدران في الضيافة الأكبر جيبًا مغلقًا صافيه 1.26 م²، رغم عدم وجود فتحة مغلقة في اتحاد محاور الغرف. أُسنِد إلى حمام النساء وأُعيد تدقيقه؛ زادت مساحة مضلعات الغرف المحسوبة 1.84 م² مع بقاء الغلاف العام. أضيفت قاعدة محدودة لهذه الجيوب، وعُدّل اختيار النوافذ لترك مسافة عن التقاء الجدران. أُعيد التصدير بعد زوال W_FLOOR_UNASSIGNED وW_OPENING_AT_JUNCTION اللذين ظهرا أثناء المراجعة.

## التحقق وحدوده

تحققنا من البرنامج والارتدادات وعدم التداخل والمساحات بعد الحجوزات ومسارات الأسرة والضيوف وخصوصية الحمامات الملحقة والوصول بين الدورين. فحص الخصوصية خطوط نظر بعينات محدودة، ولا يثبت خصوصية كل موضع أو الجوار أو الأدوار. رفضت الاختبارات إسقاط الغرفة الثانية أو فتح باب مباشر من مجلس الرجال إليها. ورُفض اتجاه غير مدعوم مع حذف الرسم القديم. نجح مسار pipeline كامل على برنامج العائلية دون إخراج رسومات إضافية للعرض في اختبار التكامل.

لا أخطاء ترجمة أو تشخيصات تصدير. strict لا يمر دون استثناءات: بقيت تحذيرات غياب تجهيزات المطبخ والحمامات المقصود مع تعليق التأثيث، وتفضيل الأداة للنوافذ الجنوبية الذي ليس تحليل شمس أو كودًا، وبعض تعليقات المصدر. لا تحذيرات هندسية أخرى غير مراجعة في الحالات المسلّمة. الرسومات إنجليزية ودون أبعاد أو مساحات مكتوبة لهذه الأداة وفق التوجيه السابق.

الأعمدة حجوزات تنسيق فقط؛ لم نثبت كفاية عددها أو بحور السقف أو النظام الجانبي، ولم نحسب الأحمال والترخيم والتربة والأساسات والتسليح. خلوص السلم مشروط بافتراض البلاطة والغطاء دون كمرات ساقطة في المسار. لا اعتماد كودي سعودي/يمني، ولا فحص تأثيث أو مناورة سيارة أو تصريف أسطح. هذه ليست مخططات تنفيذية.

نطاق النجاح المقاس ثلاثة برامج، وأرض مستطيلة بشارع جنوبي ووصول سلم شمالي، وأنواع الفراغات والأدوار التنظيمية في الأمثلة. لا ندعي دعم كل البرامج والاتجاهات. UNKNOWN يعني عدم العثور على شاهد ضمن المهلة، وINFEASIBLE هنا يخص النموذج والقيود المحددة؛ لا يثبتان استحالة تصميم العميل على نحو عام. FEASIBLE لا تعني الحل الأمثل أو اعتماد الجودة البصرية.

## الملفات والتشغيل

GROUND_PROGRAM_COMPARISON.pdf يعرض الأرضيات الثلاثة ثم الأدوار الأولى. لكل حالة داخل cases ملفات الطلب والحل والتنسيق وVILLA.arch وPDF/PNG/SVG/DXF للمسقطين. مصدر ArchLang الكامل هو مرجع الربط الرأسي؛ Plan JSON الجزئي لا يحفظ جميع عناصره. الحلول المعروضة هي ملفات جذور الحالات مع ACCEPTANCE.json؛ المحاولات الأولى وسجلات التشخيص الأخرى مرفقة للشفافية.

بعد تثبيت requirements.txt وnpm install:

`python pipeline.py --request cases/family_two_bedrooms/REQUEST.json --out output/new_case --seconds 35`

الطلب يحدد فراغات كل دور ونوعها ومساحتها وعرضها الأدنى وروابط الوصول والمداخل ومجموعات الضيوف والأسرة. min_area وmin_side في هذه الأمثلة اختيارات اختبارية وليست اشتراطات محلية. استخدم pipeline للطلبات الجديدة؛ run_ground_cases مساعد تجهيز، وليس واجهة توليد عامة. التلميحات مضمّنة وغير مقفلة. استُخدمت المكتبات المحلية دون خدمات مدفوعة أو وكلاء إضافيين. النتائج متعددة الخيوط وقد تختلف عند الإعادة. لم يُنشر التطوير أو يُستأنف الفرع المؤرشف.
'''
(ROOT/'REPORT_AR.md').write_text(report)
(ROOT/'README.md').write_text('Start with REPORT_AR.md and VIEW.html. Install requirements.txt and npm dependencies, then use pipeline.py with an explicit REQUEST.json. Verify delivered cases with verify_ground_programs.py. make_cases.py defines the benchmark programmes. All structural reservations are preliminary; published site and A2 remain unchanged.\n')
cards=[]
for i,name in enumerate(order):
    s=v['cases'][name];cards.append(f'<article><h2>{arabic[i]}</h2><p>وظائف: {s["requested_ground_functions"]} · غرف نوم أرضية: {s["ground_bedrooms"]} · مداخل: {s["ground_entrances"]}</p><a href="cases/{name}/COORD_GROUND.pdf">الأرضي PDF</a> · <a href="cases/{name}/COORD_FIRST.pdf">الأول PDF</a><img src="cases/{name}/COORD_GROUND.png"><details><summary>اعرض الدور الأول</summary><img src="cases/{name}/COORD_FIRST.png"></details><p>مضلعات الأرضي عند المحاور: {s["ground_gross_room_polygons_m2"]:.2f} م²</p></article>')
(ROOT/'VIEW.html').write_text('<!doctype html><html lang="ar" dir="rtl"><meta charset="utf-8"><title>ثلاثة برامج أرضية</title><style>body{font:19px sans-serif;background:#f5f3ef;color:#23483d;margin:24px}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(380px,1fr));gap:18px}article{background:white;padding:16px;border-radius:12px}img{width:100%}</style><h1>ثلاثة برامج أرضية على أرض 30×35</h1><p>نتائج بحثية محدودة، ليست مخططات تنفيذية أو اعتمادًا إنشائيًا. الموقع لم يتغير.</p><a href="GROUND_PROGRAM_COMPARISON.pdf">لوحة المقارنة PDF</a> · <a href="REPORT_AR.md">التقرير والحدود</a><main>'+''.join(cards)+'</main></html>')
target=ROOT.parent/'ANT_GROUND_PROGRAM_SOLVER_RESULTS.zip'
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(ROOT.rglob('*')):
        if p.is_file() and not p.is_symlink() and not any(k in p.parts for k in ['node_modules','.venv','__pycache__']):z.write(p,'ANT_GROUND_PROGRAM_SOLVER/'+str(p.relative_to(ROOT)))
with zipfile.ZipFile(target) as z:assert z.testzip() is None
print(json.dumps({'zip':str(target),'bytes':target.stat().st_size,'cases':len(v['cases'])}))
