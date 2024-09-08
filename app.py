from flask import Flask, render_template, request, redirect, url_for, flash, make_response, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
from io import BytesIO, StringIO
import base64
import os
import csv
import json
from supabase import create_client, Client

app = Flask(__name__)

# Supabase setup
supabase_url = os.environ.get("SUPABASE_URL", "https://jynejmfngqrblrpmzgbr.supabase.co")
supabase_key = os.environ.get("SUPABASE_KEY",
                              "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imp5bmVqbWZuZ3FyYmxycG16Z2JyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MjM4ODM5NTEsImV4cCI6MjAzOTQ1OTk1MX0.w_qWvc0o1bICOBZMGL7wA3KEE1elfPDX7oVquVhvchU")

if not supabase_url or not supabase_key:
    raise ValueError("Supabase URL and key must be set in environment variables.")

supabase: Client = create_client(supabase_url, supabase_key)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your_fallback_secret_key')

login_manager = LoginManager(app)
login_manager.login_view = 'login'


class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

from uuid import UUID
@login_manager.user_loader
def load_user(user_id):
    try:
        # Validate that user_id is a valid UUID
        UUID(user_id)
        user_data = supabase.table('users').select('*').eq('id', user_id).execute()
        if user_data.data:
            return User(id=user_data.data[0]['id'], username=user_data.data[0]['username'])
    except ValueError:
        # If user_id is not a valid UUID, handle the error
        return None


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = generate_password_hash(password)

        existing_user = supabase.table('users').select('*').eq('username', username).execute()
        if existing_user.data:
            flash('Username already exists. Please choose a different one.', 'danger')
            return redirect(url_for('register'))

        new_user = supabase.table('users').insert({'username': username, 'password': hashed_password}).execute()
        if new_user.data:
            flash('Your account has been created! You can now log in.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Registration failed. Please try again.', 'danger')

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user_data = supabase.table('users').select('*').eq('username', username).execute()
        if user_data.data and check_password_hash(user_data.data[0]['password'], password):
            user = User(id=user_data.data[0]['id'], username=user_data.data[0]['username'])
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            flash('Login unsuccessful. Please check username and password', 'danger')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/')
@login_required
def index():
    tasks = supabase.table('tasks').select('*').eq('user_id', current_user.id).order('priority', desc=True).execute()
    current_date = datetime.now()  # Ensure current datetime is naive
    tasks_by_category = {}
    for task in tasks.data:
        due_date = datetime.fromisoformat(task['due_date']).replace(tzinfo=None) if task['due_date'] else None

        if task['done']:
            task['status'] = 'completed-on-time' if due_date and due_date >= current_date else 'completed-late'
        else:
            task['status'] = 'overdue' if due_date and due_date < current_date else 'pending'

        category = task['category'] or 'Uncategorized'
        if category not in tasks_by_category:
            tasks_by_category[category] = []
        tasks_by_category[category].append(task)

    return render_template('index.html', tasks_by_category=tasks_by_category, chart_url=url_for('completion_chart'))


@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_task():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        priority = int(request.form['priority'])
        due_date_str = request.form['due_date']
        if due_date_str:
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d').replace(tzinfo=None)  # Ensure naive datetime
        else:
            due_date = None
        category = request.form['category']

        new_task = {
            'title': title,
            'description': description,
            'priority': priority,
            'due_date': due_date.isoformat() if due_date else None,
            'category': category,
            'user_id': current_user.id,
            'done': False
        }

        task_result = supabase.table('tasks').insert(new_task).execute()

        if task_result.data:
            new_task_id = task_result.data[0]['id']

            subtasks = request.form.getlist('subtasks')
            for subtask_content in subtasks:
                if subtask_content.strip():
                    supabase.table('subtasks').insert({
                        'content': subtask_content,
                        'done': False,
                        'task_id': new_task_id
                    }).execute()

            supabase.table('task_history').insert({
                'task_id': new_task_id,
                'change_type': 'created',
                'details': json.dumps(new_task)
            }).execute()

        return redirect(url_for('index'))
    return render_template('add_task.html')


@app.route('/update/<int:id>', methods=['GET', 'POST'])
@login_required
def update_task(id):
    task = supabase.table('tasks').select('*').eq('id', id).eq('user_id', current_user.id).execute()
    if not task.data:
        return redirect(url_for('index'))

    task = task.data[0]

    if request.method == 'POST':
        old_task_data = task.copy()

        task['title'] = request.form['title']
        task['description'] = request.form['description']
        task['priority'] = int(request.form['priority'])
        due_date_str = request.form.get('due_date')
        if due_date_str:
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d').replace(tzinfo=None)  # Ensure naive datetime
            task['due_date'] = datetime.combine(due_date, datetime.min.time()).isoformat()
        else:
            task['due_date'] = None
        task['done'] = 'done' in request.form
        task['category'] = request.form['category']

        supabase.table('tasks').update(task).eq('id', id).execute()

        # Handle subtasks...
        return redirect(url_for('index'))

    subtasks = supabase.table('subtasks').select('*').eq('task_id', id).execute()
    return render_template('update_task.html', task=task, subtasks=subtasks.data)

@app.route('/delete/<int:id>')
@login_required
def delete_task(id):
    task = supabase.table('tasks').select('*').eq('id', id).eq('user_id', current_user.id).execute()
    if task.data:
        task_dict = task.data[0]
        supabase.table('tasks').delete().eq('id', id).execute()
        supabase.table('subtasks').delete().eq('task_id', id).execute()

        supabase.table('task_history').insert({
            'task_id': id,
            'change_type': 'deleted',
            'details': json.dumps(task_dict)
        }).execute()

    return redirect(url_for('index'))


@app.route('/task_history')
@login_required
def task_history():
    history = supabase.table('task_history').select('*,tasks(title)').order('change_time', desc=True).execute()
    history_data = [{
        'task_title': record['tasks']['title'],
        'change_type': record['change_type'],
        'change_time': record['change_time'],
        'details': record['details']
    } for record in history.data]
    return jsonify(history_data)


@app.route('/completion_chart')
@login_required
def completion_chart():
    tasks = supabase.table('tasks').select('*').eq('user_id', current_user.id).execute()
    completed_tasks = sum(1 for task in tasks.data if task['done'])
    total_tasks = len(tasks.data)
    incomplete_tasks = total_tasks - completed_tasks

    sns.set_style("whitegrid")
    plt.figure(figsize=(10, 6))
    colors = sns.color_palette("deep", 2)

    if total_tasks == 0:
        plt.text(0.5, 0.5, 'No tasks available',
                 horizontalalignment='center',
                 verticalalignment='center',
                 fontsize=20, color='gray')
        plt.axis('off')
    else:
        plt.pie([completed_tasks, incomplete_tasks],
                labels=['Completed', 'Incomplete'],
                autopct='%1.1f%%',
                colors=colors,
                startangle=90,
                wedgeprops={'edgecolor': 'white', 'linewidth': 2})
        plt.title('Task Completion Rates', fontsize=18, fontweight='bold', pad=20)
        plt.gca().add_artist(plt.Circle((0, 0), 0.7, fc='white'))

    img = BytesIO()
    plt.savefig(img, format='png', dpi=300, bbox_inches='tight', transparent=True)
    img.seek(0)
    plot_url = base64.b64encode(img.getvalue()).decode('utf8')

    return render_template('completion_chart.html', plot_url=plot_url)


@app.route('/task_analysis')
@login_required
def task_analysis():
    tasks = supabase.table('tasks').select('*').eq('user_id', current_user.id).execute()

    if not tasks.data:
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.text(0.5, 0.5, 'No tasks available',
                horizontalalignment='center',
                verticalalignment='center',
                fontsize=20, color='gray')
        ax.axis('off')

        img = BytesIO()
        plt.savefig(img, format='png', dpi=300, bbox_inches='tight')
        img.seek(0)
        plot_url = base64.b64encode(img.getvalue()).decode('utf8')

        analysis = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'completion_rate': "0.0%",
        }

        return render_template('task_analysis.html', plot_url=plot_url, analysis=analysis)

    df = pd.DataFrame(tasks.data)

    total_tasks = len(df)
    completed_tasks = df['done'].sum()
    completion_rate = completed_tasks / total_tasks * 100 if total_tasks > 0 else 0

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 12))

    colors = sns.color_palette("deep", 2)
    ax1.pie([completed_tasks, total_tasks - completed_tasks],
            labels=['Completed', 'Incomplete'],
            autopct='%1.1f%%',
            colors=colors,
            startangle=90,
            wedgeprops={'edgecolor': 'white', 'linewidth': 2})
    ax1.set_title('Task Completion Rate', fontsize=16, fontweight='bold')

    if 'due_date' in df.columns:
        df['due_date'] = pd.to_datetime(df['due_date'])
        df['due_date'] = df['due_date'].dt.date
        due_date_counts = df['due_date'].value_counts().sort_index()

        due_date_counts.plot(kind='bar', ax=ax2, color=colors[1], edgecolor='white')
        ax2.set_xlabel('Due Date', fontsize=14, fontweight='bold')
        ax2.set_ylabel('Number of Tasks', fontsize=14, fontweight='bold')
        ax2.set_title('Tasks by Due Date', fontsize=16, fontweight='bold')
        ax2.tick_params(axis='x', rotation=45)

    plt.tight_layout()

    img = BytesIO()
    plt.savefig(img, format='png', dpi=300, bbox_inches='tight')
    img.seek(0)
    plot_url = base64.b64encode(img.getvalue()).decode('utf8')

    analysis = {
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'completion_rate': f"{completion_rate:.1f}%",
    }

    return render_template('task_analysis.html', plot_url=plot_url, analysis=analysis)


@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        reminder_days = request.form.get('reminder_days', type=int)
        # Save the settings to the user's profile in Supabase
        supabase.table('users').update({'reminder_days': reminder_days}).eq('id', current_user.id).execute()
        flash(f'Settings updated. Reminder days set to {reminder_days}', 'success')
        return redirect(url_for('settings'))

    # Get current settings from Supabase
    user_settings = supabase.table('users').select('reminder_days').eq('id', current_user.id).execute()
    reminder_days = user_settings.data[0]['reminder_days'] if user_settings.data else None

    return render_template('settings.html', reminder_days=reminder_days)


@app.route('/export_tasks', methods=['GET'])
@login_required
def export_tasks():
    format = request.args.get('format', 'csv')
    tasks = supabase.table('tasks').select('*').eq('user_id', current_user.id).execute()

    if format == 'csv':
        return export_tasks_csv(tasks.data)
    elif format == 'json':
        return export_tasks_json(tasks.data)
    else:
        flash('Invalid format specified', 'danger')
        return redirect(url_for('index'))


def export_tasks_csv(tasks):
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['ID', 'Title', 'Description', 'Done', 'Priority', 'Due Date', 'Category'])
    for task in tasks:
        cw.writerow([task['id'], task['title'], task['description'], task['done'], task['priority'], task['due_date'],
                     task['category']])

    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=tasks.csv"
    output.headers["Content-type"] = "text/csv"
    return output


def export_tasks_json(tasks):
    tasks_list = []
    for task in tasks:
        task_data = {
            'ID': task['id'],
            'Title': task['title'],
            'Description': task['description'],
            'Done': task['done'],
            'Priority': task['priority'],
            'Due Date': task['due_date'],
            'Category': task['category']
        }
        tasks_list.append(task_data)

    output = make_response(json.dumps(tasks_list, indent=4))
    output.headers["Content-Disposition"] = "attachment; filename=tasks.json"
    output.headers["Content-type"] = "application/json"
    return output


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)), debug=True)