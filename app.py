from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt
from datetime import datetime
from flask_migrate import Migrate
import os

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

    return render_template('index.html', tasks_by_category=tasks_by_category)

@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_task():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        priority = int(request.form['priority'])
        due_date_str = request.form['due_date']
        due_date = datetime.strptime(due_date_str, '%Y-%m-%d') if due_date_str else None
        category = request.form['category']
        new_task = Task(title=title, description=description, priority=priority, due_date=due_date, category=category, user_id=current_user.id)

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
@login_required
def update_task(id):
    task = Task.query.filter_by(id=id, user_id=current_user.id).first_or_404()
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
@login_required
def delete_task(id):
    task = Task.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    db.session.delete(task)
    db.session.commit()
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.drop_all()  # This will drop all existing tables
        db.create_all()  # This will create all tables from scratch
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)), debug=True)