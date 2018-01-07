from django.contrib.auth import authenticate
from django.utils.translation import ugettext_lazy as _

from rest_framework import serializers
from rest_framework_mongoengine.serializers import DocumentSerializer
from mongoengine.fields import ObjectIdField

from users.models import User


class AuthTokenSerializer(serializers.Serializer):
    username = serializers.CharField(label=_("Username"))
    password = serializers.CharField(label=_("Password"), style={'input_type': 'password'})

    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')

        if username and password:
            user = authenticate(username=username, password=password)
            if user:
                # From Django 1.10 onwards the `authenticate` call simply
                # returns `None` for is_active=False users.
                # (Assuming the default `ModelBackend` authentication backend.)
                if not user.is_active:
                    msg = _('User account is disabled.')
                    raise serializers.ValidationError(msg)
            else:
                msg = _('Unable to log in with provided credentials.')
                raise serializers.ValidationError(msg)
        else:
            msg = _('Must include "username" and "password".')
            raise serializers.ValidationError(msg)

        attrs['user'] = user
        return attrs


class UserSerializer(DocumentSerializer):
    #id = serializers.IntegerField(read_only=False)
    user_id = ObjectIdField(source='id')
    
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'bio', )
        read_only_fields = ('email', )
    

class SignUpSerializer(serializers.Serializer):
    username = serializers.CharField(
        max_length=120,
        min_length=5)
        
    email = serializers.EmailField()
    password1 = serializers.CharField(write_only=True)
    password2 = serializers.CharField(write_only=True)
    
    def validate_username(self, username):
        #TODO better username validation
        regexp = "/^[A-Za-z0-9]+(?:[ _-][A-Za-z0-9]+)*$/"
        #validate with regexp
        #check if username exists
        usr = User.objects.filter(username=username)
        if usr:
            raise serializers.ValidationError(
                _("A user is already registered with this username."))
        return username

    def validate_email(self, email):
        # Check if a already uses this email
        usr = User.objects.filter(email=email)
        if usr:
            raise serializers.ValidationError(
                _("A user is already registered with this e-mail address."))
        return email

    def validate_password1(self, password):
        #TODO better password constraints (length, uppercase, lowercase, special characters, etc)
        min_length = 8#app_settings.PASSWORD_MIN_LENGTH
        if len(password) < min_length:
            raise serializers.ValidationError(_("Password must be a minimum of {0} "
                                          "characters.").format(min_length))
        return password

    def validate(self, data):
        if data['password1'] != data['password2']:
            raise serializers.ValidationError(_("The two password fields didn't match."))
        return data

    def get_cleaned_data(self):
        return {
            'username': self.validated_data.get('username', ''),
            'password1': self.validated_data.get('password1', ''),
            'email': self.validated_data.get('email', '')
        }

    def save(self, request):
        self.cleaned_data = self.get_cleaned_data()
        new_user = User(username=self.cleaned_data['username'], email=self.cleaned_data['email'])
        new_user.set_password(self.cleaned_data['password1'])
        new_user.save()
        return new_user

    
class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(max_length=128)
    new_password1 = serializers.CharField(max_length=128)
    new_password2 = serializers.CharField(max_length=128)

    def __init__(self, *args, **kwargs):
        super(PasswordChangeSerializer, self).__init__(*args, **kwargs)
        self.error_messages = {
        'password_mismatch': _("The two password fields didn't match."),
        'password_constraints': _("Password constraints not respected."),
        }
        self.request = self.context.get('request')
        self.user = getattr(self.request, 'user', None)

    def validate_old_password(self, value):
        invalid_password_conditions = (
            self.user,
            not self.user.check_password(value)
        )

        if all(invalid_password_conditions):
            raise serializers.ValidationError('Invalid password')
        
        return value

    def validate(self, attrs):
        # validate the passwords
        old_pwd = attrs.get('old_password')#getattr(self.request, 'old_password')
        self.validate_old_password(old_pwd)
        
        new_pwd1 = attrs.get('new_password1')
        new_pwd2 = attrs.get('new_password2')
        
        if new_pwd1 == new_pwd2:
            # validate password constraints : length and characters user
            if not self.validate_password_constraints(new_pwd1):
                # save the new password
                raise serializers.ValidationError(self.error_messages['password_constraints'])
        else:
            raise serializers.ValidationError(self.error_messages['password_mismatch'])
        
        self.new_pwd = new_pwd1
        
        return attrs
    
    def validate_password_constraints(self, pwd):
        if len(pwd) < 8:
            return False
        
        return True
        
    def save(self):
        # save the new password in the database
        self.user.set_password(self.new_pwd)
        self.user.save()
        from django.contrib.auth import update_session_auth_hash
        update_session_auth_hash(self.request, self.user)
