// scripts.js
document.addEventListener('DOMContentLoaded', function() {
    // Add smooth scrolling to all links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            document.querySelector(this.getAttribute('href')).scrollIntoView({
                behavior: 'smooth'
            });
        });
    });

    // Add animation to task list items
    const taskItems = document.querySelectorAll('li');
    taskItems.forEach((item, index) => {
        item.style.animation = `fadeIn 0.5s ease ${index * 0.1}s forwards`;
    });

    // Handle delete action
    const deleteForms = document.querySelectorAll('form[action^="/delete_task/"]');
    deleteForms.forEach(form => {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            if (confirm('Are you sure you want to delete this task?')) {
                fetch(this.action, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // Remove the task item from the DOM
                        const taskItem = this.closest('li') || this.closest('.task-item');
                        if (taskItem) {
                            taskItem.remove();
                        } else {
                            console.error('Task item not found in DOM');
                        }
                        alert('Task deleted successfully.');
                    } else {
                        console.error('Delete failed:', data.message);
                        alert(data.message || 'Failed to delete task. Please try again.');
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('An error occurred. Please try again.');
                });
            }
        });
    });
});

// Add this to your CSS file if not already present
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(20px); }
    to { opacity: 1; transform: translateY(0); }
}