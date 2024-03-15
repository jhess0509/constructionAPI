from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import text
from flask_cors import CORS
from datetime import datetime
import time

# this variable, db, will be used for all SQLAlchemy commands
db = SQLAlchemy()
# create the app
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})  # Allow requests from any origin
# change string to the name of your database; add path if necessary
db_name = 'sockmarket.db'

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_name

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True

# initialize the app with Flask-SQLAlchemy
db.init_app(app)


class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(100), nullable=False)
    companyName = db.Column(db.String(100), nullable=False)
    start = db.Column(db.Date, nullable=False)
    end = db.Column(db.Date, nullable=False)


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    projectId = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    color = db.Column(db.String(100), nullable=True)
    actionText = db.Column(db.String(100), nullable=True)
    start = db.Column(db.Date, nullable=False)
    end = db.Column(db.Date, nullable=False)


with app.app_context():
    db.create_all()


# NOTHING BELOW THIS LINE NEEDS TO CHANGE
# this route will test the database connection - and nothing more
@app.route('/data/getActiveProjects')
def getActiveProjects():
    active_projects = Project.query.filter_by(status='active').all()

    # Convert the list of Project objects to a JSON-compatible format
    active_projects_json = [
        {
            'id': project.id,
            'name': project.name,
            'companyName': project.companyName,
            'status': project.status,
            'start': str(project.start),  # Convert datetime to string for JSON serialization
            'end': str(project.end)  # Convert datetime to string for JSON serialization
        }
        for project in active_projects
    ]

    # Return the JSON response
    return jsonify(active_projects_json)

@app.route('/data/getOnHoldProjects')
def getOnHoldProjects():
    onhold_projects = Project.query.filter_by(status='on-hold').all()

    # Convert the list of Project objects to a JSON-compatible format
    onhold_projects_json = [
        {
            'id': project.id,
            'name': project.name,
            'companyName': project.companyName,
            'status': project.status,
            'start': str(project.start),  # Convert datetime to string for JSON serialization
            'end': str(project.end)  # Convert datetime to string for JSON serialization
        }
        for project in onhold_projects
    ]


    # Return the JSON response
    return jsonify(onhold_projects_json)

@app.route('/data/getCompletedProjects')
def getCompletedProjects():
    complete_projects = Project.query.filter_by(status='complete').all()

    # Convert the list of Project objects to a JSON-compatible format
    complete_projects_json = [
        {
            'id': project.id,
            'name': project.name,
            'companyName': project.companyName,
            'status': project.status,
            'start': str(project.start),  # Convert datetime to string for JSON serialization
            'end': str(project.end)  # Convert datetime to string for JSON serialization
        }
        for project in complete_projects
    ]

    # Return the JSON response
    return jsonify(complete_projects_json)


@app.post('/data/createProject')
def create():
    content = request.json
    print(content)
    start_str = content['start']
    end_str = content['end']

    start_date = convertDate(start_str)
    end_date = convertDate(end_str)

    createProject = Project(name=content['name'],
                            companyName=content['companyName'],
                            status=content['status'],
                            start=start_date,
                            end=end_date)

    db.session.add(createProject)
    db.session.flush()  # this is to get the projectID

    taskList = content['tasks']
    for task in taskList:
        task_start = task['start']
        task_end = task['end']

        task_start_date = convertDate(task_start)
        task_end_date = convertDate(task_end)
        create_task = Task(name=task['task'],
                           projectId=createProject.id,
                           start=task_start_date,
                           end=task_end_date)
        db.session.add(create_task)

    db.session.commit()
    return content

@app.route('/data/allItems', methods=['GET'])
def get_all_items():
    # Query all projects
    projects = Project.query.filter(Project.status != 'completed').all()

    # Convert projects to a JSON-compatible format
    projects_json = [
        {
            'id': project.id,
            'title': project.name,
            'companyName': project.companyName,
            'status': project.status,
            'start': str(project.start),  # Convert datetime to string for JSON serialization
            'end': str(project.end)       # Convert datetime to string for JSON serialization
        }
        for project in projects
    ]

    # Query all tasks
    tasks = Task.query.all()

    # Convert tasks to a JSON-compatible format
    tasks_json = [
        {
            'id': task.id,
            'title': task.name,
            'color': task.color,
            'actionText': task.actionText,
            'group_id': task.projectId,
            'start': task.start,
            'end' : task.end
        }
        for task in tasks
    ]

    # Create the combined JSON response
    response = {
        'groups': projects_json,
        'items': tasks_json
    }

    # Return the JSON response
    return jsonify(response)

@app.route('/data/convert_active/<int:project_id>', methods=['PUT'])
def convert_active(project_id):
    # Retrieve the project from the database
    project = Project.query.get(project_id)

    # Check if the project exists
    if project is None:
        return jsonify({'error': 'Project not found'}), 404

    # Update the status of the project to "on hold"
    project.status = 'active'

    tasks = Task.query.filter_by(projectId=project_id).all()

    # Update the titles of the tasks
    for task in tasks:
        task.color = None  # Update the title as needed
        if task.actionText is not None:
            task.title = task.title.replace(task.actionText, '')
            task.actionText = None

    # Commit the changes to the database
    db.session.commit()

    return jsonify({'message': 'Project status updated successfully', 'project': {
        'id': project.id,
        'name': project.name,
        'status': project.status,
        # Include other project attributes as needed
    }}), 200


@app.route('/data/convert_on_hold/<int:project_id>', methods=['PUT'])
def convert_on_hold(project_id):
    # Retrieve the project from the database
    project = Project.query.get(project_id)

    # Check if the project exists
    if project is None:
        return jsonify({'error': 'Project not found'}), 404

    # Update the status of the project to "on hold"
    project.status = 'on-hold'

    tasks = Task.query.filter_by(projectId=project_id).all()

    # Update the titles of the tasks
    for task in tasks:
        task.color = '#FF0000' # Update the title as needed
        if task.actionText is not None:
            task.title = task.title.replace(task.actionText, '')
            task.actionText = None



    # Commit the changes to the database
    db.session.commit()

    return jsonify({'message': 'Project status updated successfully', 'project': {
        'id': project.id,
        'name': project.name,
        'status': project.status,
        # Include other project attributes as needed
    }}), 200


@app.route('/data/convert_complete/<int:project_id>', methods=['PUT'])
def convert_complete(project_id):
    # Retrieve the project from the database
    project = Project.query.get(project_id)

    # Check if the project exists
    if project is None:
        return jsonify({'error': 'Project not found'}), 404

    # Update the status of the project to "on hold"
    project.status = 'complete'

    # Commit the changes to the database
    db.session.commit()

    return jsonify({'message': 'Project status updated successfully', 'project': {
        'id': project.id,
        'name': project.name,
        'status': project.status,
        # Include other project attributes as needed
    }}), 200


@app.route('/data/convert_action_needed/<int:id>', methods=['PUT'])
def convert_to_action_needed(id):
    # Receive the text parameter from the request body
    text = request.json.get('text')

    task = Task.query.get(id)

    # Check if the project exists
    if task is None:
        return jsonify({'error': 'Project not found'}), 404

    # Update the status of the project to "on hold"
    task.color = '#E1CA00'
    task.actionText = text
    task.name = text + task.name
    # Commit the changes to the database
    db.session.commit()

    return jsonify({'message': 'Task status updated successfully', 'project': {
        'id': task.id,
        'color': task.color,
        'actionText': task.actionText,
        # Include other project attributes as needed
    }}), 200

def convertDate(date):
    formattedDate = datetime.fromisoformat(date.replace('Z', '+00:00'))
    return formattedDate.date()


if __name__ == '__main__':
    app.run(debug=True)
