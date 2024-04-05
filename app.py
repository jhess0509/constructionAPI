from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_
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


class Holiday(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    start = db.Column(db.Date, nullable=False)
    end = db.Column(db.Date, nullable=False)


class TaskForeman(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    taskId = db.Column(db.Integer, nullable=False)


with app.app_context():
    db.create_all()


# NOTHING BELOW THIS LINE NEEDS TO CHANGE
# this route will test the database connection - and nothing more
@app.route('/data/getActiveProjects')
def getActiveProjects():
    subquery = db.session.query(Task.projectId).filter(Task.color == '#FF0000').distinct()

    # Query to find projects without tasks having color '#FF0000' or color is NULL
    projects_without_specific_color_tasks = db.session.query(Project).outerjoin(Task, Project.id == Task.projectId). \
        filter(or_(
        Task.id == None,
        Task.color != '#FF0000',
        Task.color.is_(None)  # Include condition for NULL color
    )). \
        filter(Project.id.notin_(subquery)).all()

    print(projects_without_specific_color_tasks)
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
        for project in projects_without_specific_color_tasks
    ]

    projects_copy = active_projects_json[:]

    # Iterate through the copy of the list
    for project in projects_copy:
        if project['status'] == 'complete':
            active_projects_json.remove(project)
    print(active_projects_json)

    # Return the JSON response
    return jsonify(active_projects_json)


@app.route('/data/getOnHoldProjects')
def getOnHoldProjects():
    subquery = db.session.query(Task.projectId).filter(Task.color == '#FF0000').subquery()

    # Query to join Project and the subquery
    query = db.session.query(Project).filter(Project.id.in_(subquery))

    # Execute the query to get the projects
    projects_with_specific_color_tasks = query.all()

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
        for project in projects_with_specific_color_tasks
    ]

    # Return the JSON response
    return jsonify(onhold_projects_json)


@app.route('/data/getDict')
def getDict():
    task_foremen = TaskForeman.query.all()

    # Create a dictionary where taskId is the key and name is the value
    task_foremen_dict = {foreman.taskId: foreman.name for foreman in task_foremen}

    # Return the dictionary as JSON response
    return jsonify(task_foremen_dict)


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
        db.session.flush()  # this is to get the projectID
        create_link = TaskForeman(name=content['companyName'],
                                  taskId=create_task.id)
        db.session.add(create_link)

    db.session.commit()
    return content


@app.post('/data/createTask')
def createTask():
    content = request.json
    print(content)
    start_str = content['start']
    end_str = content['end']

    start_date = convertDate(start_str)
    end_date = convertDate(end_str)

    createTask = Task(name=content['name'],
                            projectId=content['project_id'],
                            start=start_date,
                            end=end_date)
    print(createTask)

    db.session.add(createTask)
    db.session.flush()  # this is to get the projectID

    project = Project.query.get(content['project_id'])
    create_link = TaskForeman(name=project.companyName,
                              taskId=createTask.id)
    db.session.add(create_link)
    db.session.commit()
    return content


@app.route('/data/editTask', methods=['PUT'])
def edit_task():
    content = request.json
    # Retrieve the project from the database
    task = Task.query.get(content['id'])

    # Check if the project exists
    if task is None:
        return jsonify({'error': 'Task not found'}), 404

    # Update the status of the project to "on hold"
    print(convertDate(content['start']))

    task.start = convertDate(content['start'])
    task.end = convertDate(content['end'])

    tasks = Task.query.filter_by(projectId=task.projectId).all()

    for taskList in tasks:
        print(taskList)
        print(taskList.id)
        task_foreman = TaskForeman.query.filter_by(taskId=taskList.id).first()
        task_foreman.name = content['foreman']

    # Commit the changes to the database
    db.session.commit()

    return jsonify({'message': 'Task status updated successfully', 'project': {
        'id': task.id,
        'color': task.color,
        'actionText': task.actionText,
        # Include other project attributes as needed
    }}), 200






@app.post('/data/updateTask')
def updateTask():
    content = request.json
    print(content)

    task = Task.query.get(content['id'])

    if task:

        # Convert the timestamp to a Python datetime object
        start_datetime = datetime.utcfromtimestamp(content['start'])
        end_datetime = datetime.utcfromtimestamp(content['end'])
        # Extract only the date part
        start_date = start_datetime.date()
        end_date = end_datetime.date()

        print(start_date)
        # Update the attributes of the item
        task.name = content['title']  # Assuming you're updating the 'name' attribute
        task.actionText = content['actionText']
        task.color = content['color']
        task.start = start_date
        task.end = end_date

        # Commit the changes to the database session
        db.session.commit()

        return 'Item updated successfully'
    else:
        return 'Item not found', 404


@app.post('/data/createHoliday')
def createHoliday():
    content = request.json
    print(content)
    start_str = content['start']
    end_str = content['end']

    start_date = convertDate(start_str)
    end_date = convertDate(end_str)

    createHoliday = Holiday(name=content['name'],
                            start=start_date,
                            end=end_date)

    db.session.add(createHoliday)
    db.session.commit()


@app.route('/data/allItems', methods=['GET'])
def get_all_items():
    # Query all projects
    projects = Project.query.filter(Project.status != 'complete').all()

    # Convert projects to a JSON-compatible format
    projects_json = [
        {
            'id': project.id,
            'title': project.name,
            'companyName': project.companyName,
            'status': project.status,
            'start': str(project.start),  # Convert datetime to string for JSON serialization
            'end': str(project.end)  # Convert datetime to string for JSON serialization
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
            'end': task.end
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


@app.route('/data/holidays', methods=['GET'])
def get_holidays():
    # Query all projects
    holidays = Holiday.query.all()

    # Convert projects to a JSON-compatible format
    holidays_json = [
        {
            'id': holiday.id,
            'name': holiday.name,
            'start': str(holiday.start),  # Convert datetime to string for JSON serialization
            'end': str(holiday.end)  # Convert datetime to string for JSON serialization
        }
        for holiday in holidays
    ]

    # Return the JSON response
    return jsonify(holidays_json)


@app.route('/data/convert_active/<int:project_id>', methods=['PUT'])
def convert_active(project_id):
    # Retrieve the project from the database
    task = Task.query.get(project_id)

    # Check if the project exists
    if task is None:
        return jsonify({'error': 'Project not found'}), 404

    # Update the status of the project to "on hold"
    task.color = None
    if task.actionText is not None:
        task.name = task.name.replace(task.actionText, '')
        task.actionText = None
    # Commit the changes to the database
    db.session.commit()

    return jsonify({'message': 'Task status updated successfully', 'project': {
        'id': task.id,
        'color': task.color,
        'actionText': task.actionText,
        # Include other project attributes as needed
    }}), 200


@app.route('/data/convert_on_hold/<int:project_id>', methods=['PUT'])
def convert_on_hold(project_id):
    # Retrieve the project from the database
    task = Task.query.get(project_id)

    # Check if the project exists
    if task is None:
        return jsonify({'error': 'Project not found'}), 404

    # Update the status of the project to "on hold"
    task.color = '#FF0000'
    if task.actionText is not None:
        task.name = task.name.replace(task.actionText, '')
        task.actionText = None
    # Commit the changes to the database
    db.session.commit()

    return jsonify({'message': 'Task status updated successfully', 'project': {
        'id': task.id,
        'color': task.color,
        'actionText': task.actionText,
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
