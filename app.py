from flask import Flask, render_template, request, send_file, session, jsonify
from datetime import datetime, timedelta
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
import io
import ast
import random
import matplotlib.pyplot as plt
import base64

app = Flask(__name__)
app.secret_key = "study_planner_secret"  # Needed for session storage

# ---------- Motivational Tips ----------
TIPS = [
    "💧 Stay hydrated and take deep breaths!",
    "📖 Revise key points before switching subjects.",
    "🚫 Keep your phone away during study hours.",
    "✍️ Use active recall instead of just rereading.",
    "🧘 Take a stretch break during long sessions."
]

MOTIVATION_WORDS = [
    "🎉 Well done!",
    "💪 Great job!",
    "👏 Keep it up!",
    "🔥 Awesome work!",
    "🌟 You're doing amazing!"
]

# ---------- Allocate study hours ----------
def allocate_time(subjects, total_hours):
    weights = [(6 - int(s['priority'])) for s in subjects]
    total_weight = sum(weights)
    for i, subject in enumerate(subjects):
        subject['allocated_hours'] = round((weights[i] / total_weight) * total_hours, 2)

# ---------- Calculate schedule with smart breaks ----------
def calculate_schedule(subjects, start_time_str):
    start_time = datetime.strptime(start_time_str, "%H:%M")
    schedule = []
    current_time = start_time
    hours_studied = 0
    total_session_time = 0

    for s in sorted(subjects, key=lambda x: int(x['priority'])):
        hours = s['allocated_hours']
        end_time = current_time + timedelta(hours=hours)
        schedule.append({
            'name': s['name'],
            'hours': hours,
            'start': current_time.strftime("%I:%M %p"),
            'end': end_time.strftime("%I:%M %p"),
            'type': 'study'
        })
        current_time = end_time
        hours_studied += hours
        total_session_time += hours

        # Smart Breaks
        if hours_studied >= 0.5 and total_session_time < 2:  # after 30 mins
            break_end = current_time + timedelta(minutes=5)
            schedule.append({
                'name': "Quick Break",
                'hours': 0.08,
                'start': current_time.strftime("%I:%M %p"),
                'end': break_end.strftime("%I:%M %p"),
                'type': 'break'
            })
            current_time = break_end
            hours_studied = 0

        elif total_session_time >= 2:  # after 2 hrs
            break_end = current_time + timedelta(minutes=15)
            schedule.append({
                'name': "Long Break",
                'hours': 0.25,
                'start': current_time.strftime("%I:%M %p"),
                'end': break_end.strftime("%I:%M %p"),
                'type': 'break'
            })
            current_time = break_end
            total_session_time = 0
            hours_studied = 0

    return schedule

# ---------- Generate Pie Chart ----------
def generate_pie_chart(schedule):
    subjects = [s['name'] for s in schedule if s['type'] == 'study']
    hours = [s['hours'] for s in schedule if s['type'] == 'study']

    if not subjects or not hours:
        return None

    fig, ax = plt.subplots()
    ax.pie(hours, labels=subjects, autopct='%1.1f%%', startangle=90)
    ax.axis('equal')

    # Save to buffer
    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    buf.seek(0)
    chart_base64 = base64.b64encode(buf.read()).decode("utf-8")
    plt.close(fig)
    return chart_base64

# ---------- Export schedule to PDF ----------
@app.route('/download_pdf', methods=['POST'])
def download_pdf():
    schedule = session.get("schedule")
    if not schedule:
        return "No schedule to download", 400

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []

    styles = getSampleStyleSheet()
    elements.append(Paragraph("Study Schedule", styles['Title']))

    data = [["Subject", "Hours", "Start", "End"]]
    for s in schedule:
        data.append([s['name'], str(s['hours']), s['start'], s['end']])

    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.green),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
    ]))
    elements.append(table)

    doc.build(elements)
    buffer.seek(0)

    return send_file(buffer, as_attachment=True, download_name="study_schedule.pdf", mimetype='application/pdf')

# ---------- Mark subject as Done ----------
@app.route("/mark_done", methods=["POST"])
def mark_done():
    subject_name = request.json.get("subject")
    schedule = session.get("schedule", [])

    # Remove subject from schedule
    updated_schedule = [s for s in schedule if s['name'] != subject_name]

    session["schedule"] = updated_schedule

    return jsonify({
        "success": True,
        "motivation": random.choice(MOTIVATION_WORDS)
    })

# ---------- Home route ----------
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        total_hours = float(request.form.get('total_hours'))
        start_time = request.form.get('start_time')

        subjects = []
        for i in range(1, 6):
            name = request.form.get(f'subject{i}')
            priority = request.form.get(f'priority{i}')
            if name and priority:
                subjects.append({'name': name, 'priority': priority})

        if not subjects:
            error = "Please enter at least one subject with priority."
            return render_template('index.html', error=error)

        allocate_time(subjects, total_hours)
        schedule = calculate_schedule(subjects, start_time)

        # Save schedule in session
        session["schedule"] = schedule

        # Extra features
        tip = random.choice(TIPS)
        chart_base64 = generate_pie_chart(schedule)

        return render_template('index.html', schedule=schedule, total_hours=total_hours,
                               start_time=start_time, subjects=subjects, tip=tip, chart_base64=chart_base64)

    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
