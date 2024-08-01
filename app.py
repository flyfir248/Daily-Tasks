from flask import Flask, render_template, request, redirect, url_for, flash, make_response, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt
from datetime import datetime,timedelta
from flask_migrate import Migrate
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
from io import BytesIO,StringIO
import base64
import os
import csv
import json

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tasks.db'
app.config['SECRET_KEY'] = 'your_secret_key'  # Change this to a random secret key
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
migrate = Migrate(app, db)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    tasks = db.relationship('Task', backref='user', lazy=True)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(200), nullable=True)
    done = db.Column(db.Boolean, default=False)
    priority = db.Column(db.Integer, default=1)
    due_date = db.Column(db.DateTime, nullable=True)
    category = db.Column(db.String(50), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subtasks = db.relationship('Subtask', backref='task', lazy=True, cascade="all, delete-orphan")
    history = db.relationship('TaskHistory', backref='task', lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'done': self.done,
            'priority': self.priority,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'category': self.category,
            'user_id': self.user_id
        }
    @property
    def progress(self):
        if not self.subtasks:
            return 100 if self.done else 0
        completed_subtasks = sum(1 for subtask in self.subtasks if subtask.done)
        return int((completed_subtasks / len(self.subtasks)) * 100)

    @property
    def progress(self):
        if not self.subtasks:
            return 100 if self.done else 0
        completed_subtasks = sum(1 for subtask in self.subtasks if subtask.done)
        return int((completed_subtasks / len(self.subtasks)) * 100)

class Subtask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(200), nullable=False)
    done = db.Column(db.Boolean, default=False)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists. Please choose a different one.', 'danger')
            return redirect(url_for('register'))
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(username=username, password=hashed_password)
        db.session.add(user)
        db.session.commit()
        app.logger.info(f"New user registered: {username}")
        flash('Your account has been created! You can now log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        app.logger.info(f"Login attempt for user: {username}")
        if user:
            app.logger.info("User found in database")
            if bcrypt.check_password_hash(user.password, password):
                app.logger.info("Password is correct")
                login_user(user)
                next_page = request.args.get('next')
                return redirect(next_page) if next_page else redirect(url_for('index'))
            else:
                app.logger.info("Password is incorrect")
        else:
            app.logger.info("User not found in database")
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
    tasks = Task.query.filter_by(user_id=current_user.id).order_by(Task.priority.desc()).all()
    current_date = datetime.now()
    tasks_by_category = {}
    for task in tasks:
        if task.done:
            if task.due_date and task.due_date >= current_date:
                task.status = 'completed-on-time'
            else:
                task.status = 'completed-late'
        else:
            if task.due_date and task.due_date < current_date:
                task.status = 'overdue'
            else:
                task.status = 'pending'

        category = task.category or 'Uncategorized'
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
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d')
        else:
            due_date = None

        category = request.form['category']
        new_task = Task(title=title, description=description, priority=priority, due_date=due_date, category=category,
                        user_id=current_user.id)

        # Handle subtasks
        subtasks = request.form.getlist('subtasks')
        for subtask_content in subtasks:
            if subtask_content.strip():  # Ignore empty subtasks
                new_subtask = Subtask(content=subtask_content)
                new_task.subtasks.append(new_subtask)

        db.session.add(new_task)
        db.session.commit()

        # Log task creation in TaskHistory
        history = TaskHistory(task_id=new_task.id, change_type='created', details=json.dumps(new_task.to_dict()))
        db.session.add(history)
        db.session.commit()

        return redirect(url_for('index'))
    return render_template('add_task.html')


@app.route('/update/<int:id>', methods=['GET', 'POST'])
@login_required
def update_task(id):
    task = Task.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    if request.method == 'POST':
        old_task_data = task.to_dict()  # Save old task data for history

        task.title = request.form['title']
        task.description = request.form['description']
        task.priority = int(request.form['priority'])
        due_date_str = request.form.get('due_date')

        if due_date_str:
            # Manually parse the due date string to ensure no time component
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
            task.due_date = datetime.combine(due_date, datetime.min.time())
        else:
            task.due_date = None

        task.done = 'done' in request.form
        task.category = request.form['category']

        # Handle subtasks
        existing_subtasks = {subtask.id: subtask for subtask in task.subtasks}
        subtask_contents = request.form.getlist('subtasks')
        subtask_ids = request.form.getlist('subtask_ids')
        subtask_dones = request.form.getlist('subtask_dones')

        for i, content in enumerate(subtask_contents):
            if content.strip():
                if subtask_ids[i]:  # Existing subtask
                    subtask = existing_subtasks.pop(int(subtask_ids[i]))
                    subtask.content = content
                    subtask.done = subtask_ids[i] in subtask_dones
                else:  # New subtask
                    new_subtask = Subtask(content=content)
                    task.subtasks.append(new_subtask)

        # Remove subtasks that were deleted
        for subtask in existing_subtasks.values():
            db.session.delete(subtask)

        db.session.commit()

        # Log task update in TaskHistory
        new_task_data = task.to_dict()
        history = TaskHistory(
            task_id=task.id,
            change_type='updated',
            details=json.dumps({
                'old_data': old_task_data,
                'new_data': new_task_data
            })
        )
        db.session.add(history)
        db.session.commit()

        return redirect(url_for('index'))
    return render_template('update_task.html', task=task)
@app.route('/delete/<int:id>')
@login_required
def delete_task(id):
    task = Task.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    task_dict = task.to_dict()  # Get the dictionary representation before deletion
    db.session.delete(task)
    db.session.commit()

    # Log task deletion in TaskHistory
    history = TaskHistory(
        task_id=id,  # Use the id directly as task object is deleted
        change_type='deleted',
        details=json.dumps(task_dict)
    )
    db.session.add(history)
    db.session.commit()

    return redirect(url_for('index'))

@app.route('/task_history')
@login_required
def task_history():
    history = TaskHistory.query.filter_by(task_id=current_user.id).order_by(TaskHistory.change_time.desc()).all()
    history_data = [{
        'task_title': record.task.title,
        'change_type': record.change_type,
        'change_time': record.change_time.strftime('%Y-%m-%d %H:%M:%S'),
        'details': record.details
    } for record in history]
    return jsonify(history_data)


@app.route('/completion_chart')
@login_required
def completion_chart():
    tasks = Task.query.filter_by(user_id=current_user.id).all()
    completed_tasks = sum(1 for task in tasks if task.done)
    total_tasks = len(tasks)
    incomplete_tasks = total_tasks - completed_tasks

    # Set the style for a more professional look
    sns.set_style("whitegrid")
    plt.figure(figsize=(10, 6))

    # Create a more appealing color palette
    colors = sns.color_palette("deep", 2)

    if total_tasks == 0:
        # Handle the case when there are no tasks
        plt.text(0.5, 0.5, 'No tasks available',
                 horizontalalignment='center',
                 verticalalignment='center',
                 fontsize=20, color='gray')
        plt.axis('off')
    else:
        # Create the pie chart
        plt.pie([completed_tasks, incomplete_tasks],
                labels=['Completed', 'Incomplete'],
                autopct='%1.1f%%',
                colors=colors,
                startangle=90,
                wedgeprops={'edgecolor': 'white', 'linewidth': 2})

        # Add a title with custom font
        plt.title('Task Completion Rates', fontsize=18, fontweight='bold', pad=20)

        # Add a subtle shadow for depth
        plt.gca().add_artist(plt.Circle((0,0), 0.7, fc='white'))

    # Save the plot
    img = BytesIO()
    plt.savefig(img, format='png', dpi=300, bbox_inches='tight', transparent=True)
    img.seek(0)
    plot_url = base64.b64encode(img.getvalue()).decode('utf8')

    return render_template('completion_chart.html', plot_url=plot_url)


@app.route('/task_analysis')
@login_required
def task_analysis():
    tasks = Task.query.filter_by(user_id=current_user.id).all()
    history = TaskHistory.query.filter(TaskHistory.task_id.in_([task.id for task in tasks])).all()

    if not tasks:
        # Handle case when there are no tasks
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

    # Create a DataFrame with available attributes
    df = pd.DataFrame([(task.title, task.done, task.due_date) for task in tasks],
                      columns=['title', 'done', 'due_date'])

    # Basic statistics
    total_tasks = len(df)
    completed_tasks = df['done'].sum()
    completion_rate = completed_tasks / total_tasks * 100 if total_tasks > 0 else 0

    # Create visualizations
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 12))

    # 1. Pie chart for completion rate
    colors = sns.color_palette("deep", 2)
    ax1.pie([completed_tasks, total_tasks - completed_tasks],
            labels=['Completed', 'Incomplete'],
            autopct='%1.1f%%',
            colors=colors,
            startangle=90,
            wedgeprops={'edgecolor': 'white', 'linewidth': 2})
    ax1.set_title('Task Completion Rate', fontsize=16, fontweight='bold')

    # 2. Bar chart for tasks by due date (if available)
    if 'due_date' in df.columns:
        df['due_date'] = pd.to_datetime(df['due_date'])
        df['due_date'] = df['due_date'].dt.date  # Extract date part only
        due_date_counts = df['due_date'].value_counts().sort_index()

        due_date_counts.plot(kind='bar', ax=ax2, color=colors[1], edgecolor='white')
        ax2.set_xlabel('Due Date', fontsize=14, fontweight='bold')
        ax2.set_ylabel('Number of Tasks', fontsize=14, fontweight='bold')
        ax2.set_title('Tasks by Due Date', fontsize=16, fontweight='bold')
        ax2.tick_params(axis='x', rotation=45)

    plt.tight_layout()

    # Save the plot as a base64-encoded string
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
        # Save the settings to the user's profile or a separate settings table
        # For now, we'll just flash a message
        flash(f'Settings updated. Reminder days set to {reminder_days}', 'success')
        return redirect(url_for('settings'))
    return render_template('settings.html')


@app.route('/export_tasks', methods=['GET'])
@login_required
def export_tasks():
    format = request.args.get('format', 'csv')
    tasks = Task.query.filter_by(user_id=current_user.id).all()

    if format == 'csv':
        return export_tasks_csv(tasks)
    elif format == 'json':
        return export_tasks_json(tasks)
    else:
        flash('Invalid format specified', 'danger')
        return redirect(url_for('index'))


def export_tasks_csv(tasks):
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['ID', 'Title', 'Description', 'Done', 'Priority', 'Due Date', 'Category'])
    for task in tasks:
        cw.writerow([task.id, task.title, task.description, task.done, task.priority, task.due_date, task.category])

    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=tasks.csv"
    output.headers["Content-type"] = "text/csv"
    return output


def export_tasks_json(tasks):
    tasks_list = []
    for task in tasks:
        task_data = {
            'ID': task.id,
            'Title': task.title,
            'Description': task.description,
            'Done': task.done,
            'Priority': task.priority,
            'Due Date': task.due_date.isoformat() if task.due_date else None,
            'Category': task.category
        }
        tasks_list.append(task_data)

    output = make_response(json.dumps(tasks_list, indent=4))
    output.headers["Content-Disposition"] = "attachment; filename=tasks.json"
    output.headers["Content-type"] = "application/json"
    return output



class TaskHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    change_type = db.Column(db.String(50), nullable=False)  # e.g., 'created', 'updated', 'completed', 'deleted'
    change_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    details = db.Column(db.Text, nullable=True)

if __name__ == '__main__':
    with app.app_context():
        db.drop_all()  # This will drop all existing tables
        db.create_all()  # This will create all tables from scratch
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)), debug=True)