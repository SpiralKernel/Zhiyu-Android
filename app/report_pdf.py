"""用与网页一致的五色方案生成中文家长报告，不依赖浏览器服务。"""
from io import BytesIO
from datetime import datetime
from zoneinfo import ZoneInfo
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether

BG='#FFF8F5';BLUSH='#F5E2DA';CORAL='#E4A28F';BLUE='#85A9AF';INK='#3B3838'
pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))


def render(value):
    out=BytesIO();width=174*mm
    style=ParagraphStyle('body',fontName='STSong-Light',fontSize=10,leading=17,textColor=colors.HexColor(INK),wordWrap='CJK',spaceAfter=7)
    title=ParagraphStyle('title',parent=style,fontSize=24,leading=34,spaceAfter=12)
    heading=ParagraphStyle('heading',parent=style,fontSize=15,leading=24,spaceBefore=15,spaceAfter=9)
    small=ParagraphStyle('small',parent=style,fontSize=8,leading=13,textColor=colors.HexColor('#625E5D'))
    def p(text,st=style):return Paragraph(escape(str(text)).replace('\n','<br/>'),st)
    stage_title = value.get('book_title') if value.get('stage') == 'senior' else f"{value['student']['grade']}年级{('全一册·'+('前半进度' if value['student']['term']==1 else '后半进度')) if value.get('subject')=='physics' and value['student']['grade']==9 else ('上册' if value['student']['term']==1 else '下册')}{value.get('subject_name','数学')}"
    story=[p('学习，一步一步看得见。',title),p(f"{value['student']['nickname']} / {stage_title} / {value['period_label']}",style),p('生成于 '+datetime.fromisoformat(value['generated_at']).astimezone(ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M')+' 北京时间',small),Spacer(1,10*mm)]
    counts=value['summary']
    cards=Table([[p('题库作答',small),p('有效独立作答',small),p('AI提问',small),p('导入题目',small)],
                 [p(str(counts[k]),title) for k in ('attempts','independent','questions','imported')]],colWidths=[width/4]*4)
    cards.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),colors.HexColor(BLUSH)),('BOX',(0,0),(-1,-1),.6,colors.HexColor(CORAL)),('LEFTPADDING',(0,0),(-1,-1),12),('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),8)]))
    story.extend([cards,p('章节学习分布',heading),p('截至当前的题型状态；未评估表示还缺证据，不表示不会。',small)])
    chart=Drawing(width,34+len(value['chapters'])*37)
    labels=[('stable','表现稳定',BLUE),('weak','需要补强',CORAL),('learning','学习中',BLUSH),('unknown','未评估',BG)]
    for i,(_,label,color) in enumerate(labels):
        chart.add(Rect(i*110,chart.height-10,7,7,fillColor=colors.HexColor(color),strokeColor=colors.HexColor(BLUSH)))
        chart.add(String(i*110+12,chart.height-10,label,fontName='STSong-Light',fontSize=8,fillColor=colors.HexColor(INK)))
    for i,chapter in enumerate(value['chapters']):
        y=chart.height-35-i*37
        chart.add(String(0,y,chapter['name'],fontName='STSong-Light',fontSize=9,fillColor=colors.HexColor(INK)))
        chart.add(String(width-45,y,str(chapter['total'])+'种题型',fontName='STSong-Light',fontSize=8,fillColor=colors.HexColor(INK)))
        x=0
        for key,_,color in labels:
            n=chapter[key]
            if not n:continue
            segment=width*n/max(1,chapter['total'])
            chart.add(Rect(x,y-19,max(0,segment-2),10,rx=2,ry=2,fillColor=colors.HexColor(color),strokeColor=colors.HexColor(BLUSH) if key=='unknown' else None))
            x+=segment
    story.append(chart)
    if value['trend']:
        trend_intro=[p('练习的脚步',heading),p('按有作答记录的日期展示。蓝灰为独立练习，珊瑚为辅助练习，浅桃为其它已记录作答。',small)]
        daily=value['trend'][-14:];trend=Drawing(width,110);maximum=max(1,max(v['independent']+v['assisted']+v['other'] for v in daily));step=width/max(4,len(daily));bar=min(25,step-10)
        for i,v in enumerate(daily):
            x=i*step+(step-bar)/2;y=22
            for key,color in [('independent',BLUE),('assisted',CORAL),('other',BLUSH)]:
                height=v[key]/maximum*65
                if height:trend.add(Rect(x,y,bar,height,fillColor=colors.HexColor(color),strokeColor=None));y+=height
            trend.add(String(x,y+5,str(v['independent']+v['assisted']+v['other']),fontName='STSong-Light',fontSize=8,fillColor=colors.HexColor(INK)))
            trend.add(String(x-3,7,v['day'][5:],fontName='STSong-Light',fontSize=7,fillColor=colors.HexColor(INK)))
        story.append(KeepTogether(trend_intro+[trend]))
    if value.get('review_queue'):
        story.extend([p('值得再检查一下',heading),p('距上次独立验证较久，建议用新题复测；不表示已经不会。',small)])
        for item in value['review_queue']:story.append(p(item['name']))
    analysis=value['analysis'];story.extend([p('AI 学情分析' if value['analysis_source']=='ai' else '学习记录摘要',heading),p(analysis['summary'])])
    for text in analysis.get('strengths',[]):story.append(p('进展：'+text))
    names={t['id']:t['name'] for t in value['types']}
    for focus in analysis.get('focus',[]):
        story.append(p(names.get(focus['type_id'],'重点关注')+'：'+focus['finding']))
        for eid in focus['evidence_ids']:
            evidence=next((e for e in value['evidence'] if e['id']==eid),{})
            story.append(p('依据：'+str(evidence.get('stem') or evidence.get('quote') or eid)[:180]+('；'+str(evidence['note']) if evidence.get('note') else ''),small))
    story.extend([p('下一步，怎样支持孩子',heading)])
    for i,text in enumerate(analysis.get('parent_actions',[]),1):story.append(p(f'{i}. '+text))
    for text in analysis.get('next_steps',[]):story.append(p('学习安排：'+text))
    if value['types']:
        story.append(p('题型观察',heading))
        rows=[[p('题型',small),p('独立作答',small),p('当前观察',small)]]
        for t in value['types'][:25]:rows.append([p(t['name']),p(t['independent_count']),p(t.get('current_status') or t.get('learning_status') or t['status'])])
        table=Table(rows,colWidths=[88*mm,25*mm,61*mm],repeatRows=1)
        table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor(BLUSH)),('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,-1),.4,colors.HexColor(BLUSH)),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
        story.append(table)
    story.extend([Spacer(1,6*mm),p('判断边界：'+analysis['uncertainty'],small),p('对话、图片识别与来源答案仍需核对；本报告不提供未经校准的能力百分比。',small)])
    def page(canvas,doc):
        canvas.saveState();canvas.setFillColor(colors.HexColor(BG));canvas.rect(0,0,210*mm,297*mm,fill=1,stroke=0)
        canvas.setFillColor(colors.HexColor(CORAL));canvas.rect(18*mm,282*mm,174*mm,2*mm,fill=1,stroke=0)
        canvas.setFont('STSong-Light',8);canvas.setFillColor(colors.HexColor(INK));canvas.drawString(18*mm,12*mm,'知域 / 家长学情报告');canvas.drawRightString(192*mm,12*mm,str(doc.page));canvas.restoreState()
    doc=SimpleDocTemplate(out,pagesize=(210*mm,297*mm),leftMargin=18*mm,rightMargin=18*mm,topMargin=23*mm,bottomMargin=23*mm,title='知域 家长学情报告',author='知域')
    doc.build(story,onFirstPage=page,onLaterPages=page)
    return out.getvalue()
