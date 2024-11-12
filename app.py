import os

from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_, UniqueConstraint
from sqlalchemy.sql import text
from flask_cors import CORS
from datetime import datetime, timezone, timedelta
import time
import sqlite3
from config import Config
import psycopg2
import csv


# create the app
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})  # Allow requests from any origin
# change string to the name of your database; add path if necessary
# Specify the folder where you want to store the database file
db_name = 'sockmarket.db'

# Update PostgreSQL URI here
app.config.from_object(Config)  # Load the configuration from the Config class

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True

db = SQLAlchemy(app)


class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(100), nullable=False)
    companyName = db.Column(db.String(100), nullable=False)
    start = db.Column(db.Date, nullable=False)
    end = db.Column(db.Date, nullable=False)

    def delete(self):
        db.session.delete(self)
        db.session.commit()


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
    __tablename__ = 'task_foreman'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    taskId = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)

    # Define unique constraint for the taskId column
    __table_args__ = (
        UniqueConstraint('taskId', name='unique_task_id'),
    )

class Foreman(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    firstName = db.Column(db.String(100), nullable=False)
    lastName = db.Column(db.String(100), nullable=False)


class TaskList(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(100), nullable=True)
    task = db.Column(db.String(100), nullable=True)


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


@app.route('/data/getTaskList')
def getTaskList():
    task_list = TaskList.query.all()

    taskList_json = [
        {
            'id': taskList.id,
            'type': taskList.type,
            'task': taskList.task,  # Convert datetime to string for JSON serialization  # Convert datetime to string for JSON serialization
        }
        for taskList in task_list
    ]

    # Return the JSON response
    return jsonify(taskList_json)


@app.route('/data/<int:project_id>', methods=['DELETE'])
def delete_project(project_id):
    project = Project.query.get_or_404(project_id)
    project.delete()
    return jsonify({'message': 'Project deleted successfully'})


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
    start_str = content['start']
    end_str = content['end']

    start_date = convertDate(start_str)
    end_date = convertDate(end_str)

    print(start_str)
    print(end_str)
    print(start_date)
    print(end_date)

    createTask = Task(name=content['name'],
                      projectId=content['project_id'],
                      start=start_date,
                      end=end_date)

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

    task.start = convertDate(content['start'])
    task.end = convertDate(content['end'])

    task_foreman = TaskForeman.query.filter_by(taskId=task.id).first()
    print(content['start'])
    print(content['end'])
    print(task.start)
    print(task.end)
    task_foreman.name = content['foreman']

    project = Project.query.get(task.projectId)
    project.companyName = content['foreman']

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

    task = Task.query.get(content['id'])

    if task:
        # Convert the timestamp to a Python datetime object
        start_datetime_utc = datetime.fromtimestamp(content['start'], timezone.utc)
        end_datetime_utc = datetime.fromtimestamp(content['end'], timezone.utc)
        print(start_datetime_utc)
        print(end_datetime_utc)

        # Extract date in UTC
        start_date = start_datetime_utc.date()
        end_date = end_datetime_utc.date()

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
    start_str = content['start']
    end_str = content['end']

    start_date = convertDate(start_str)
    end_date = convertDate(end_str)

    createHoliday = Holiday(name=content['name'],
                            start=start_date,
                            end=end_date)

    db.session.add(createHoliday)
    db.session.commit()


@app.post('/data/createTaskList')
def createTaskList():

    try:
        content = request.json
        createTaskList = TaskList(task=content['task'],
                                  type=None)

        db.session.add(createTaskList)
        db.session.commit()
        return jsonify({'message': 'Task created successfully'}), 200
    except:
        return jsonify({'error': 'Error'}), 404


@app.route('/data/taskList/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    task = TaskList.query.get(task_id)
    if task:
        db.session.delete(task)
        db.session.commit()
        return jsonify({'message': 'Task deleted successfully'}), 200
    else:
        return jsonify({'error': 'Task not found'}), 404


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


@app.route('/data/delete/<int:task_id>', methods=['PUT'])
def delete(task_id):
    # Retrieve the project from the database
    task = Task.query.get(task_id)

    # Check if the project exists
    if task is None:
        return jsonify({'error': 'Project not found'}), 404

    if task:
        db.session.delete(task)
        db.session.commit()
        return jsonify({'message': 'Task Removed', 'project': {
            'id': task.id,
            # Include other project attributes as needed
        }}), 200

    else:
        return jsonify({'error': 'Task not found'}), 404


def convertDate(date):
    formattedDate = datetime.fromisoformat(date.replace('Z', '+00:00'))
    return formattedDate.date()


# Create Endpoint
@app.route('/foremen', methods=['POST'])
def create_foreman():
    data = request.get_json()
    new_foreman = Foreman(firstName=data['firstname'], lastName=data['lastname'])
    db.session.add(new_foreman)
    db.session.commit()
    return jsonify({'message': 'Foreman created successfully'}), 201


@app.route('/foremen', methods=['GET'])
def get_all_foremen():
    foremen = Foreman.query.all()
    result = []
    for foreman in foremen:
        result.append({'id': foreman.id, 'firstname': foreman.firstName, 'lastname': foreman.lastName})
    return jsonify(result), 200


@app.route('/foremen/<int:id>', methods=['PUT'])
def edit_foreman(id):
    foreman = Foreman.query.get_or_404(id)
    data = request.get_json()
    foreman.firstName = data['firstName']
    foreman.lastName = data['lastName']
    db.session.commit()
    return jsonify({'message': 'Foreman updated successfully'}), 200


@app.route('/foremen/<int:id>', methods=['DELETE'])
def delete_foreman(id):
    foreman = Foreman.query.get_or_404(id)
    db.session.delete(foreman)
    db.session.commit()
    return jsonify({'message': 'Foreman deleted successfully'}), 200


# saving initial foreman information
@app.route('/foremen/migrate', methods=['GET'])
def save_foremen():
    foremen_data = [
        {'firstname': 'Donnell', 'lastname': 'Soler'},
        {'firstname': 'Norberto', 'lastname': 'Reyes Hernandez'},
        {'firstname': 'Flavio', 'lastname': 'Serrano Gonzalez'},
        {'firstname': 'Jose', 'lastname': 'Resendiz Soto'},
        {'firstname': 'Rendi', 'lastname': 'Venegas-Cruz'},
        {'firstname': 'Gerardo', 'lastname': 'Chavez Rojo'},
        {'firstname': 'Thomas', 'lastname': 'Arthur'},
        {'firstname': 'Francisco', 'lastname': 'Hernandez'},
        {'firstname': 'Richard', 'lastname': 'Lovely'},
        {'firstname': 'Chad', 'lastname': 'White'},
        {'firstname': 'Matt', 'lastname': 'Gesner'},
        {'firstname': 'Gary', 'lastname': 'Christie'},
        {'firstname': 'Shaun', 'lastname': 'Ware'},
        {'firstname': 'Stephen', 'lastname': 'Fowler'},
        {'firstname': 'Thomas', 'lastname': 'Burgess'},
        {'firstname': 'David', 'lastname': 'McDaniel'},
        {'firstname': 'Eric', 'lastname': 'Rodrigues'},
        {'firstname': 'Brett', 'lastname': 'Parsley'},
        {'firstname': 'Jonathan', 'lastname': 'Smith'},
        {'firstname': 'Adam', 'lastname': 'Hart'},
        {'firstname': 'Darren', 'lastname': 'McManus'},
        {'firstname': 'Mark', 'lastname': 'Collins'},
        {'firstname': 'Hager', 'lastname': 'McCune'},
        {'firstname': 'David', 'lastname': 'Harwell'},
        {'firstname': 'Keith', 'lastname': 'Breedlove'},
        {'firstname': 'William', 'lastname': 'Whitlow'},
        {'firstname': 'Jeffrey', 'lastname': 'Whittington'},
        {'firstname': 'Margarito', 'lastname': 'Mejia Romero'},
        {'firstname': 'Nectali', 'lastname': 'Bueso Canales'},
        {'firstname': 'Henry', 'lastname': 'Brown'},
        {'firstname': 'Brian', 'lastname': 'Lemon'},
        {'firstname': 'Jason', 'lastname': 'Prince'},
        {'firstname': 'Sergio', 'lastname': 'Almanza Navarro'},
        {'firstname': 'Tyler', 'lastname': 'Birdsong'},
        {'firstname': 'Carlos', 'lastname': 'Sanchez Farfan'},
        {'firstname': 'Christopher', 'lastname': 'Chalk'},
        {'firstname': 'Oscar', 'lastname': 'Martinez Tobar'},
        {'firstname': 'Christopher', 'lastname': 'Perry'},
        {'firstname': 'Marco', 'lastname': 'Avila Pena'},
        {'firstname': 'Brandon', 'lastname': 'Ledford'},
        {'firstname': 'Kary', 'lastname': 'Combs'},
        {'firstname': 'Joshua', 'lastname': 'Coley'},
        {'firstname': 'Daniel', 'lastname': 'Outwater'},
        {'firstname': 'Mark', 'lastname': 'Collins'},
        {'firstname': 'Gregory', 'lastname': 'Leatherman'},
        {'firstname': 'Jeffrey', 'lastname': 'Turman'},
        {'firstname': 'Benjamin', 'lastname': 'Hubbard'},
        {'firstname': 'Michael', 'lastname': 'Romeo'},
        {'firstname': 'Cory', 'lastname': 'Blackwell'},
        {'firstname': 'Scott', 'lastname': 'Barbee'},
        {'firstname': 'Richard', 'lastname': 'Birdsong'},
        {'firstname': 'Lindsay', 'lastname': 'Austin'},
        {'firstname': 'Rhett', 'lastname': 'Cox'},
        {'firstname': 'Brandon', 'lastname': 'Ervin'},
        {'firstname': 'Austin', 'lastname': 'Locklear'},
        {'firstname': 'David', 'lastname': 'Mangiamele'},
        {'firstname': 'Donnie', 'lastname': 'Doster'},
        {'firstname': 'Drew', 'lastname': 'Barnett'},
        {'firstname': 'Jeff', 'lastname': 'Crump'}
    ]
    for foreman_info in foremen_data:
        new_foreman = Foreman(firstName=foreman_info['firstname'], lastName=foreman_info['lastname'])
        db.session.add(new_foreman)
    db.session.commit()
    # Save foremen into the database


# saving initial taskList information
@app.route('/data/migrate', methods=['GET'])
def save_taskList():
    project_tasks = [
        {'type': 'Clear & Grub / Demolition', 'task': 'Traffic Control'},
        {'type': 'Clear & Grub / Demolition', 'task': 'Clear & Grub'},
        {'type': 'Clear & Grub / Demolition', 'task': 'Asphalt Demolition'},
        {'type': 'Clear & Grub / Demolition', 'task': 'Curb Demolition'},
        {'type': 'Clear & Grub / Demolition', 'task': 'Sawcutting'},
        {'type': 'Clear & Grub / Demolition', 'task': 'Demo Concrete Sidewalk/Flatwork'},
        {'type': 'Clear & Grub / Demolition', 'task': 'Building Demolition'},
        {'type': 'Clear & Grub / Demolition', 'task': 'Select Brush Removal'},
        {'type': 'Clear & Grub / Demolition', 'task': 'Fence Removal'},
        {'type': 'Clear & Grub / Demolition', 'task': 'Remove Existing Storm Pipe'},
        {'type': 'Clear & Grub / Demolition', 'task': 'Remove Existing Storm Drainage Structure'},

        {'type': 'Erosion Control', 'task': 'Construction Entrance'},
        {'type': 'Erosion Control',
         'task': 'Concrete Washout Pit, Note: washout/spoinls for other trades is not included'},
        {'type': 'Erosion Control', 'task': 'Truck Wash (Installation / Removal)'},
        {'type': 'Erosion Control',
         'task': 'Truck Wash (Sitework labor), truck wash fees, labor for other trades not included'},
        {'type': 'Erosion Control', 'task': 'Silt Fence'},
        {'type': 'Erosion Control', 'task': 'Burlap Baffle Fence'},
        # ... (other erosion control tasks)

        {'type': 'Rough Grading', 'task': 'Topsoil (Strip 6" & Place On site)'},
        {'type': 'Rough Grading', 'task': 'Topsoil (Respread On site)'},
        # ... (other rough grading tasks)

        {'type': 'Fine Grading', 'task': 'Fine Grade Building Pad (+-0.1\')'},
        {'type': 'Fine Grading', 'task': 'Fine Grade Curb (+-0.1\')'},
        # ... (other fine grading tasks)

        {'type': 'Storm Drainage', 'task': 'Outlet Control Structure'},
        {'type': 'Storm Drainage', 'task': 'Area Drain'},
        # ... (other storm drainage tasks)

        {'type': 'Detention System', 'task': 'Excavate for Detention System (Stockpile On Site)'},
        {'type': 'Detention System', 'task': 'Excavate for Detention System (Waste Off Site)'},
        # ... (other detention system tasks)

        {'type': 'Sand Filter', 'task': 'Excavate for Sand Filter (Waste Off Site)'},
        {'type': 'Sand Filter', 'task': '6" Perforated PVC'},
        # ... (other sand filter tasks)

        {'type': 'Roof Drains', 'task': '4" HDPE Roof Drain'},
        {'type': 'Roof Drains', 'task': '6" HDPE Roof Drain'},
        # ... (other roof drain tasks)

        {'type': 'Water System', 'task': 'Tap / Meter Assembly'},
        {'type': 'Water System', 'task': 'Tie Into Water Meter (Installed by Others)'},
        # ... (other water system tasks)

        {'type': 'Sewer System', 'task': 'Tie Into CO/MH at ROW Line'},
        {'type': 'Sewer System', 'task': 'Sanitary Sewer Manhole'},
        # ... (other sewer system tasks)

        {'type': 'Concrete', 'task': '6" Vertical Curb'},
        {'type': 'Concrete', 'task': '18" Curb & Gutter'},
        # ... (other concrete tasks)

        {'type': 'Asphalt Paving', 'task': '6" ABC Stone Placement (LDP)'},
        {'type': 'Asphalt Paving', 'task': '8" ABC Stone Placement (HDP)'},
        # ... (other asphalt paving tasks)

        {'type': 'Misc Items', 'task': 'Gray Modular Block Retaining Wall w/ Certification'},
        {'type': 'Misc Items', 'task': 'Brick Pavers / Decorative Concrete / Base Course'},
    ]
    for taskList in project_tasks:
        new_TaskList = TaskList(type=taskList['type'], task=taskList['task'])
        db.session.add(new_TaskList)
    db.session.commit()
    # Save foremen into the database


if __name__ == '__main__':
    app.run(debug=True)
