# -*- coding: utf-8 -*-
from flask import Blueprint, g
from flask_restful import Resource, reqparse, Api, abort

from app import db
from app.auth.models import User
from app import app

from itsdangerous import (
    TimedJSONWebSignatureSerializer as Serializer,
    BadSignature,
    SignatureExpired
)

import redis

mod = Blueprint('auth', __name__, url_prefix='/api/v1')

api = Api(app)

# Helper functions
def create_new_user(email, password):
    if email is None or password is None:
        abort(400)
    if User.query.filter_by(email=email).first() is not None:
        abort(400)
    user = User(email=email, password=password)
    db.session.add(user)
    db.session.commit()
    return user

def list_of_users():
    users = User.query.all()
    return {"users": [u.to_json for u in users]}

def generate_token(user, expiration=3600):
    s = Serializer(app.config['SECRET_KEY'], expires_in=expiration)
    return s.dumps({'uid': user.uid })


def validate_token(token):
    s = Serializer(app.config['SECRET_KEY'])
    try:
        data = s.loads(token)
    except SignatureExpired:
        return None
    except BadSignature:
        return None
    user = User.query.get(data['uid'])
    g.current_user = user
    return user

def authenticate(email, password):
    user = User.query.filter_by(email=email).first()
    if user is None:
        abort(400)
    if user.verify_password(password):
        g.current_user = user
        return user
    return None
    

# Resource representing a single user
class UserResource(Resource):
    parser = reqparse.RequestParser()
    parser.add_argument('password', type=str)
    parser.add_argument('email', type=str)

    def post(self):
        """ Create a new user """
        args = self.parser.parse_args(strict=True)
        try:
            user = create_new_user(args['email'], args['password'])
            return user.to_json, 200
        except:
            abort(400)

    def get(self, email):
        """ Return information about a single user """
        user = User.query.get(email)
        print user
        if not user:
            abort(400)
        return user.to_json, 200

# Resource representing a list of users
class UserList(Resource):
    def get(self):
        """ Return a list of users """
        users = list_of_users()
        if not users:
            abort(400)
        return users, 200

# Authenticate a user's username/password, returns a token upon success
class LoginUser(Resource):
    parser = reqparse.RequestParser()
    parser.add_argument('email', type=str)
    parser.add_argument('password', type=str)

    def post(self):
        """ Create json web token for a valid user """
        args = self.parser.parse_args(strict=True)
        user = authenticate(args['email'], args['password'])
        if user is None:
            abort(400)
        token = generate_token(user)

        """  Store token in remote redis  """
        client = redis.StrictRedis(host='172.17.0.2', port=6379, db=0)
        client.set(token, "true")

        """  Return token """
        return {'token': token.decode('utf-8'), 'duration': 3600}, 200

# Determines if a json web token is valid for a given user account
class ValidateToken(Resource):
    parser = reqparse.RequestParser()
    parser.add_argument('token', type=str)

    def post(self):
        args = self.parser.parse_args(strict=True)
        client = redis.StrictRedis(host='172.17.0.2', port=6379, db=0)
        if client.get(args['token']) == "true":
            user = validate_token(args['token'])
            if user is None:
                abort(400)
            return {'user': user.to_json}, 200
        

# Endpoints
api.add_resource(UserResource,
                 '/account',
                 '/account/<int:user_id>')
api.add_resource(UserList, '/account/list')
api.add_resource(LoginUser, '/account/login')
api.add_resource(ValidateToken, '/account/authenticate')

