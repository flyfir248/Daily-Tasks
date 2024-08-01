# Flask Todo App

## Overview

This is a dynamic todo application built using Flask, designed to help users manage and track their tasks efficiently. The app features user authentication, task categorization, subtask management, and various analytical tools to visualize task completion rates and due dates. 

## Features

- **User Authentication**: Secure user registration and login using hashed passwords.
- **Task Management**: Create, update, delete, and mark tasks as complete.
- **Subtask Management**: Add and manage subtasks within tasks.
- **Task Categorization**: Organize tasks by categories.
- **Task Priority**: Assign priority levels to tasks.
- **Due Dates**: Set and manage due dates for tasks.
- **Task Progress**: Track progress of tasks based on subtasks completion.
- **Analytics**: Visualize task completion rates and due dates using charts.
- **Responsive UI**: User-friendly interface with feedback and notifications.

## Installation

### Prerequisites

- Python 3.x
- Flask
- Flask-SQLAlchemy
- Flask-Login
- Flask-Bcrypt
- Flask-Migrate
- Matplotlib
- Seaborn
- Pandas

### Steps

1. **Clone the repository**:
    ```sh
    git clone https://github.com/yourusername/todo-flask-app.git
    cd todo-flask-app
    ```

2. **Create a virtual environment**:
    ```sh
    python3 -m venv venv
    source venv/bin/activate
    ```

3. **Install the dependencies**:
    ```sh
    pip install -r requirements.txt
    ```

4. **Set up the database**:
    ```sh
    flask db init
    flask db migrate -m "Initial migration."
    flask db upgrade
    ```

5. **Run the application**:
    ```sh
    flask run
    ```

    The app will be available at `http://127.0.0.1:5000/`.

## Usage

### User Registration

- Navigate to `/register` to create a new account.
- Provide a unique username and password.

### User Login

- Navigate to `/login` to log in to your account.
- Enter your registered username and password.

### Dashboard

- The main dashboard (`/`) displays tasks categorized by their status and categories.
- Use the dashboard to view and manage your tasks.

### Adding Tasks

- Navigate to `/add` to create a new task.
- Provide the task title, description, priority, due date, and category.
- Add subtasks if needed.

### Updating Tasks

- Navigate to `/update/<task_id>` to update a specific task.
- Modify the task details and manage subtasks.

### Deleting Tasks

- Navigate to `/delete/<task_id>` to delete a specific task.

### Task History

- Navigate to `/task_history` to view the history of changes made to tasks.

### Task Analytics

- Navigate to `/completion_chart` to view the completion rate of tasks.
- Navigate to `/task_analysis` to analyze tasks with visualizations.

### Settings

- Navigate to `/settings` to customize user-specific settings such as reminder days.

## Configuration

### Environment Variables

- **`SQLALCHEMY_DATABASE_URI`**: The URI for the database. Default is `sqlite:///tasks.db`.
- **`SECRET_KEY`**: A secret key for session management. Ensure this is set to a secure random value.

### Example `.env` file

```env
SQLALCHEMY_DATABASE_URI=sqlite:///tasks.db
SECRET_KEY=your_secret_key
```

## Folder Structure

```
todo-flask-app/
│
├── app.py                  # Main application file
├── requirements.txt        # Python dependencies
├── migrations/             # Database migrations
├── templates/              # HTML templates
│   ├── index.html
│   ├── register.html
│   ├── login.html
│   ├── add_task.html
│   ├── update_task.html
│   ├── completion_chart.html
│   ├── task_analysis.html
│   ├── settings.html
│   └── ...
├── static/                 # Static files (CSS, JS, images)
│   ├── css/
│   ├── js/
│   └── ...
└── ...
```

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any improvements or bug fixes.
