from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tasks.db'
app.config['SECRET_KEY'] = 'your_secret_key'
db = SQLAlchemy(app)

class Subtask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(200), nullable=False)
    done = db.Column(db.Boolean, default=False)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(200), nullable=True)
    done = db.Column(db.Boolean, default=False)
    priority = db.Column(db.Integer, default=1)
    due_date = db.Column(db.DateTime, nullable=True)
    category = db.Column(db.String(50), nullable=True)  # New field
    subtasks = db.relationship('Subtask', backref='task', lazy=True, cascade="all, delete-orphan")


@app.route('/')
def index():
    tasks = Task.query.order_by(Task.priority.desc()).all()
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

    return render_template('index.html', tasks_by_category=tasks_by_category)


@app.route('/add', methods=['GET', 'POST'])
def add_task():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        priority = int(request.form['priority'])
        due_date_str = request.form['due_date']
        due_date = datetime.strptime(due_date_str, '%Y-%m-%d') if due_date_str else None
        category = request.form['category']
        new_task = Task(title=title, description=description, priority=priority, due_date=due_date, category=category)

        # Handle subtasks
        subtasks = request.form.getlist('subtasks')
        for subtask_content in subtasks:
            if subtask_content.strip():  # Ignore empty subtasks
                new_subtask = Subtask(content=subtask_content)
                new_task.subtasks.append(new_subtask)

        db.session.add(new_task)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('add_task.html')


@app.route('/update/<int:id>', methods=['GET', 'POST'])
def update_task(id):
    task = Task.query.get_or_404(id)
    if request.method == 'POST':
        task.title = request.form['title']
        task.description = request.form['description']
        task.priority = int(request.form['priority'])
        due_date_str = request.form['due_date']
        task.due_date = datetime.strptime(due_date_str, '%Y-%m-%d') if due_date_str else None
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
        return redirect(url_for('index'))
    return render_template('update_task.html', task=task)

@app.route('/delete/<int:id>')
def delete_task(id):
    task = Task.query.get_or_404(id)
    db.session.delete(task)
    db.session.commit()
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
