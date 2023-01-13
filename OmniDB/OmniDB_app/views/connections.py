import json
import os
import time
import io

import paramiko
from django.db.models import Q
from django.http import JsonResponse
from sshtunnel import SSHTunnelForwarder

from OmniDB import settings
from OmniDB_app.include import OmniDatabase
from OmniDB_app.models import Technology, Connection, Group, GroupConnection
from OmniDB_app.views.memory_objects import user_authenticated
from OmniDB_app.utils.crypto import encrypt, decrypt
from OmniDB_app.utils.key_manager import key_manager


@user_authenticated
def get_connections(request):
    v_return = {'v_data': '', 'v_error': False, 'v_error_id': -1}

    json_object = json.loads(request.POST.get('data', None))
    v_tab_conn_id_list = json_object['p_conn_id_list']

    v_tech_list = [tech.name for tech in Technology.objects.all()]

    v_connection_list = []
    connections = Connection.objects.filter(Q(user=request.user) | Q(public=True))

    if connections and key_manager.get(request.user):
        for conn in connections:

            v_conn_object = {
                'id': conn.id,
                'locked': False,
                'public': conn.public,
                'is_mine': conn.user.id == request.user.id,
                'technology': conn.technology.name,
                'alias': conn.alias,
                'conn_string': '',
                'server': '',
                'port': '',
                'service': '',
                'user': '',
                'tunnel': {
                    'enabled': conn.use_tunnel,
                    'server': conn.ssh_server,
                    'port': conn.ssh_port,
                    'user': conn.ssh_user,
                    'password': False if conn.ssh_password.strip() == '' else True,
                    'key': False if conn.ssh_key.strip() == '' else True
                }
            }

            if conn.id in v_tab_conn_id_list:
                v_conn_object['locked'] = True

            if conn.technology.name != 'terminal':
                v_conn_object['conn_string'] = conn.conn_string
                v_conn_object['server'] = conn.server
                v_conn_object['port'] = conn.port
                v_conn_object['service'] = conn.database
                v_conn_object['user'] = conn.username
                v_conn_object['password'] = False if conn.password.strip() == '' else True

            v_connection_list.append(v_conn_object)

    v_return['v_data'] = {
        'v_conn_list': v_connection_list,
        'v_technologies': v_tech_list
    }

    return JsonResponse(v_return)


@user_authenticated
def get_groups(request):
    v_return = {'v_data': [], 'v_error': False, 'v_error_id': -1}

    # Invalid session
    if not request.session.get('omnidb_session'):
        v_return['v_error'] = True
        v_return['v_error_id'] = 1
        return JsonResponse(v_return)

    groups = Group.objects.filter(user=request.user)

    if groups:
        for group in groups:
            v_current_group_data = {
                'id': group.id,
                'name': group.name,
                'conn_list': []
            }
            group_conn = GroupConnection.objects.filter(group=group)
            if group_conn:
                for conn in group_conn:
                    v_current_group_data['conn_list'].append(conn.connection.id)

            v_return['v_data'].append(v_current_group_data)

    return JsonResponse(v_return)


@user_authenticated
def new_group(request):
    v_return = {'v_data': '', 'v_error': False, 'v_error_id': -1}

    # Invalid session
    if not request.session.get('omnidb_session'):
        v_return['v_error'] = True
        v_return['v_error_id'] = 1
        return JsonResponse(v_return)

    json_object = json.loads(request.POST.get('data', None))
    p_name = json_object['p_name']

    try:
        if not p_name.strip():
            v_return['v_data'] = "Group name can not be empty"
            v_return['v_error'] = True
            return JsonResponse(v_return)

        new_group = Group(user=request.user, name=p_name)
        new_group.save()
    except Exception as exc:
        v_return['v_data'] = str(exc)
        v_return['v_error'] = True
        return JsonResponse(v_return)

    return JsonResponse(v_return)


@user_authenticated
def edit_group(request):
    v_return = {'v_data': '', 'v_error': False, 'v_error_id': -1}

    json_object = json.loads(request.POST.get('data', None))
    p_id = json_object['p_id']
    p_name = json_object['p_name']

    try:
        group = Group.objects.get(id=p_id)

        if group.user.id != request.user.id:
            v_return['v_data'] = 'This group does not belong to you.'
            v_return['v_error'] = True

            return JsonResponse(v_return)

        if not p_name.strip():
            v_return['v_data'] = "Group name can not be empty."
            v_return['v_error'] = True

            return JsonResponse(v_return)

        group.name = p_name
        group.save()
    except Exception as exc:
        v_return['v_data'] = str(exc)
        v_return['v_error'] = True
        return JsonResponse(v_return)

    return JsonResponse(v_return)


@user_authenticated
def delete_group(request):
    v_return = {'v_data': '', 'v_error': False, 'v_error_id': -1}

    json_object = json.loads(request.POST.get('data', None))
    p_id = json_object['p_id']

    try:
        group = Group.objects.get(id=p_id)

        if group.user.id != request.user.id:
            v_return['v_data'] = 'This group does not belong to you.'
            v_return['v_error'] = True

            return JsonResponse(v_return)

        group.delete()
    except Exception as exc:
        v_return['v_data'] = str(exc)
        v_return['v_error'] = True
        return JsonResponse(v_return)

    return JsonResponse(v_return)


@user_authenticated
def test_connection(request):
    v_return = {'v_data': '', 'v_error': False, 'v_error_id': -1}
    # Invalid session
    if not request.session.get('omnidb_session'):
        v_return['v_error'] = True
        v_return['v_error_id'] = 1
        return JsonResponse(v_return)

    json_object = json.loads(request.POST.get('data', None))
    p_type = json_object['type']

    password = json_object['password'].strip()
    ssh_password = json_object['tunnel']['password'].strip()
    ssh_key = json_object['tunnel']['key']

    if json_object['id'] != -1:
        conn = Connection.objects.get(id=json_object['id'])
        if json_object['password'].strip() == '':
            password = conn.password
        if json_object['tunnel']['password'].strip() == '':
            ssh_password = conn.ssh_password
        if json_object['tunnel']['key'].strip() == '':
            ssh_key = conn.ssh_key

    if json_object['temp_password']:
        password = json_object['temp_password']

    if p_type == 'terminal':

        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            # ssh key provided
            if ssh_key.strip() != '':
                key = paramiko.RSAKey.from_private_key(io.StringIO(ssh_key), password=ssh_password)
                client.connect(hostname=json_object['tunnel']['server'], username=json_object['tunnel']['user'],
                               key_filename=key, passphrase=ssh_password,
                               port=int(json_object['tunnel']['port']))
            else:
                client.connect(hostname=json_object['tunnel']['server'], username=json_object['tunnel']['user'],
                               password=ssh_password, port=int(json_object['tunnel']['port']))

            client.close()
            v_return['v_data'] = 'Connection successful.'
        except Exception as exc:
            v_return['v_data'] = str(exc)
            v_return['v_error'] = True
    else:

        database = OmniDatabase.Generic.InstantiateDatabase(
            p_type,
            json_object['server'],
            json_object['port'],
            json_object['database'],
            json_object['user'],
            password,
            -1,
            '',
            p_conn_string=json_object['connstring'],
            p_parse_conn_string=True
        )

        # create tunnel if enabled
        if json_object['tunnel']['enabled']:

            try:
                if ssh_key.strip() != '':
                    key = paramiko.RSAKey.from_private_key(io.StringIO(ssh_key), password=ssh_password)
                    server = SSHTunnelForwarder(
                        (json_object['tunnel']['server'], int(json_object['tunnel']['port'])),
                        ssh_username=json_object['tunnel']['user'],
                        ssh_private_key_password=ssh_password,
                        ssh_pkey=key,
                        remote_bind_address=(database.v_active_server, int(database.v_active_port)),
                        logger=None
                    )
                else:
                    server = SSHTunnelForwarder(
                        (json_object['tunnel']['server'], int(json_object['tunnel']['port'])),
                        ssh_username=json_object['tunnel']['user'],
                        ssh_password=ssh_password,
                        remote_bind_address=(database.v_active_server, int(database.v_active_port)),
                        logger=None
                    )
                server.set_keepalive = 120
                server.start()

                database.v_connection.v_host = '127.0.0.1'
                database.v_connection.v_port = server.local_bind_port

                message = database.TestConnection()
                server.close()
                v_return['v_data'] = message
                if message != 'Connection successful.':
                    v_return['v_error'] = True

            except Exception as exc:
                v_return['v_data'] = str(exc)
                v_return['v_error'] = True

        else:
            message = database.TestConnection()
            v_return['v_data'] = message
            if message != 'Connection successful.':
                v_return['v_error'] = True

    return JsonResponse(v_return)


@user_authenticated
def save_connection(request):
    v_return = {'v_data': '', 'v_error': False, 'v_error_id': -1}

    v_session = request.session.get('omnidb_session')
    key = key_manager.get(request.user)

    json_object = json.loads(request.POST.get('data', None))
    p_id = json_object['id']
    try:
        # New connection
        if p_id == -1:
            password = ''
            tunnel_password = ''
            if json_object['password']:
                password = encrypt(json_object['password'], key)
            if json_object['tunnel']['password'] != '':
                tunnel_password = encrypt(json_object['tunnel']['password'], key)
            if json_object['tunnel']['key'] != '':
                tunnel_key = encrypt(json_object['tunnel']['key'], key)
            conn = Connection(
                user=request.user,
                technology=Technology.objects.get(name=json_object['type']),
                server=json_object['server'],
                port=json_object['port'],
                database=json_object['database'],
                username=json_object['user'],
                password=password,
                alias=json_object['title'],
                ssh_server=json_object['tunnel']['server'],
                ssh_port=json_object['tunnel']['port'],
                ssh_user=json_object['tunnel']['user'],
                ssh_password=tunnel_password,
                ssh_key=tunnel_key,
                use_tunnel=json_object['tunnel']['enabled'],
                conn_string=json_object['connstring'],
                public=False

            )
            conn.save()
        # update
        else:
            conn = Connection.objects.get(id=p_id)

            if conn.user.id != request.user.id:
                v_return['v_data'] = 'This connection does not belong to you.'
                v_return['v_error'] = True
                return JsonResponse(v_return)

            conn.technology = Technology.objects.get(name=json_object['type'])
            conn.server = json_object['server']
            conn.port = json_object['port']
            conn.database = json_object['database']
            conn.username = json_object['user']
            if json_object['password'].strip() != '':
                conn.password = encrypt(json_object['password'], key)
            conn.alias = json_object['title']
            conn.ssh_server = json_object['tunnel']['server']
            conn.ssh_port = json_object['tunnel']['port']
            conn.ssh_user = json_object['tunnel']['user']
            if json_object['tunnel']['password'].strip() != '':
                conn.ssh_password = encrypt(json_object['tunnel']['password'], key)
            if json_object['tunnel']['key'].strip() != '':
                conn.ssh_key = encrypt(json_object['tunnel']['password'], key)

            conn.use_tunnel = json_object['tunnel']['enabled']
            conn.conn_string = json_object['connstring']
            conn.save()

        tunnel_information = {
            'enabled': conn.use_tunnel,
            'server': conn.ssh_server,
            'port': conn.ssh_port,
            'user': conn.ssh_user,
            'password': decrypt(conn.ssh_password, key) if conn.ssh_password else '',
            'key': decrypt(conn.ssh_key, key) if conn.ssh_key else ''
        }
        # this is for sqlite3 db connection because it has no password
        password = decrypt(conn.password, key) if conn.password else ''
        database = OmniDatabase.Generic.InstantiateDatabase(
            conn.technology.name,
            conn.server,
            conn.port,
            conn.database,
            conn.username,
            password,
            conn.id,
            conn.alias,
            p_conn_string=conn.conn_string,
            p_parse_conn_string=True
        )

        prompt_password = conn.password == ''

        v_session.AddDatabase(conn.id, conn.technology.name, database, prompt_password, tunnel_information, conn.alias,
                              json_object['public'])

    except Exception as exc:
        v_return['v_data'] = str(exc)
        v_return['v_error'] = True
        return JsonResponse(v_return)

    request.session['omnidb_session'] = v_session

    return JsonResponse(v_return)


@user_authenticated
def delete_connection(request):
    v_return = {'v_data': '', 'v_error': False, 'v_error_id': -1}

    v_session = request.session.get('omnidb_session')

    json_object = json.loads(request.POST.get('data', None))
    p_id = json_object['id']

    try:
        conn = Connection.objects.get(id=p_id)

        if conn.user.id != request.user.id:
            v_return['v_data'] = 'This connection does not belong to you.'
            v_return['v_error'] = True
            return JsonResponse(v_return)

        conn.delete()
        v_session.RemoveDatabase(p_id)
    except Exception as exc:
        v_return['v_data'] = str(exc)
        v_return['v_error'] = True
        return JsonResponse(v_return)

    request.session['omnidb_session'] = v_session

    return JsonResponse(v_return)


@user_authenticated
def save_group_connections(request):
    v_return = {'v_data': '', 'v_error': False, 'v_error_id': -1}

    json_object = json.loads(request.POST.get('data', None))
    p_group = json_object['p_group']
    p_conn_data_list = json_object['p_conn_data_list']

    group_obj = Group.objects.get(id=p_group)

    for v_conn_data in p_conn_data_list:
        try:
            if not v_conn_data['selected']:
                conn = GroupConnection.objects.get(group=group_obj,
                                                   connection=Connection.objects.get(id=v_conn_data['id']))
                conn.delete()
            else:
                conn = GroupConnection(
                    group=group_obj,
                    connection=Connection.objects.get(id=v_conn_data['id'])
                )
                conn.save()

        except Exception as exc:
            None

    return JsonResponse(v_return)
