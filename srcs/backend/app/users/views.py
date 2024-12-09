from django.shortcuts import render
from django.db import models
from datetime import datetime, timedelta
from django.conf import settings
from django.contrib.auth import authenticate
from rest_framework import viewsets
from rest_framework import status
from rest_framework import permissions
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.generics import UpdateAPIView, RetrieveAPIView, ListAPIView
from .models import User, UserStats, Friend, BlacklistedToken
from .serializers import UserRegistrationSerializer, UserLoginSerializer, \
    UserProfileSerializer, UserProfileSearchSerializer, UserUpdateSerializer, \
    UserStatsSerializer, FriendSerializer
import jwt
from .jwt_logic import generate_jwt, decode_jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

class UserRegistrationAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({'message': 'User successfully registered.'}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UserLoginAPIView(APIView):
    permission_classes = [permissions.AllowAny]
    """
    Handles user authentication and returns JWT tokens upon success.
    """
    def post(self, request):
        # Extract username and password from the request
        username = request.data.get("username")
        password = request.data.get("password")

        if not username or not password:
            return Response({"error": "Username and password are required."}, status=status.HTTP_400_BAD_REQUEST)

        # Authenticate user
        user = authenticate(username=username, password=password)
        if not user:
            # Authentication failed
            return Response({"error": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)
        
        user.set_online()
        # Access token (15 minutes)
        
        access_payload = {
            "user_id": user.id,
            "username": user.username,
            "type": "access"
        }
        access_token = generate_jwt(access_payload, expiration_minutes=15)  # 15 minutes
        
        # Refresh token (7 days)
        refresh_payload = {
            "user_id": user.id,
            "type": "refresh"
        }
        refresh_token = generate_jwt(refresh_payload, expiration_minutes=7 * 24 * 60)  # 7 days
        
        return Response(
            {
                "access_token": access_token,
                "refresh_token": refresh_token
            },
            status=status.HTTP_200_OK
        )

class UserTokenRefreshAPIView(APIView):
    permission_classes = [permissions.AllowAny]
    """
    Handles refreshing of JWT tokens.
    """
    def post(self, request, *args, **kwargs):
        refresh_token = request.data.get('refresh_token')
        if not refresh_token:
            return Response({"error": "Refresh token is required."}, status=status.HTTP_400_BAD_REQUEST)
        
        if BlacklistedToken.objects.filter(token=refresh_token).exists():
            return Response({"error": "This refresh token has been revoked."}, status=status.HTTP_401_UNAUTHORIZED)
    
        try:
            payload = decode_jwt(refresh_token)
            if payload.get("type") != "refresh":
                return Response({"error": "Invalid token type."}, status=status.HTTP_400_BAD_REQUEST)
            
            # Generate new access token
            access_payload = {
                "user_id": payload["user_id"],
                "username": payload.get("username", ""),
                "type": "access"
            }
            access_token = generate_jwt(access_payload, expiration_minutes=15)  # 15 minutes
            
            return Response({"access_token": access_token}, status=status.HTTP_200_OK)
        except ExpiredSignatureError:
            return Response({"error": "Refresh token has expired."}, status=status.HTTP_401_UNAUTHORIZED)
        except InvalidTokenError:
            return Response({"error": "Invalid refresh token."}, status=status.HTTP_400_BAD_REQUEST)

# TODO: delete old revoked tokens from BlacklistedToken
class UserLogoutAPIView(APIView):
    def post(self, request):
        auth_header = request.headers.get('Authorization')
        refresh_token = request.data.get('refresh_token')

        if not auth_header:
            return Response({"error": "Access token is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not refresh_token:
            return Response({"error": "Refresh token is required."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            token_type, token = auth_header.split(' ')
            if token_type.lower() != 'bearer':
                raise AuthenticationFailed("Invalid token header format.")
            
            BlacklistedToken.objects.create(token=token)

            payload = decode_jwt(refresh_token)
            if payload.get("type") != "refresh":
                return Response({"error": "Invalid token type."}, status=status.HTTP_400_BAD_REQUEST)

            BlacklistedToken.objects.create(token=refresh_token)

            user = request.user
            user.set_offline()

            return Response({"message": "Successfully logged out."}, status=status.HTTP_200_OK)

        except ExpiredSignatureError:
            return Response({"error": "One of the tokens has already expired."}, status=status.HTTP_400_BAD_REQUEST)
        except InvalidTokenError:
            return Response({"error": "Invalid token."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class UserSearchAPIView(ListAPIView):
    serializer_class = UserProfileSearchSerializer

    def get_queryset(self):
        current_user = self.request.user

        query = self.request.query_params.get('search', '').strip()

        if not query:
            return User.objects.none()

        return User.objects.filter(username__icontains=query).exclude(id=current_user.id)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        if queryset.count() == 0 and not request.query_params.get('search', '').strip():
            return Response({"error": "Search query parameter is required."}, status=status.HTTP_400_BAD_REQUEST)

        if queryset.count() == 0:
            return Response({"error": "No users found matching the search query."}, status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

class UserProfileAPIView(RetrieveAPIView):
    queryset = User.objects.all()
    serializer_class = UserProfileSerializer

    def get_serializer_context(self):
        return {'request': self.request}

    def get_object(self):
        user_id = self.kwargs.get('user_id', None)
        if user_id:
            return User.objects.get(id=user_id)
        return self.request.user

    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)

        friend_id = self.kwargs.get('user_id')
        if friend_id and request.user.id != int(friend_id):
            try:
                friend_id = int(friend_id)
                friendship = Friend.objects.filter(
                    models.Q(user=request.user, friend_id=friend_id) |
                    models.Q(user_id=friend_id, friend=request.user)
                ).first()

                if friendship:
                    response.data['friendship_status'] = friendship.status
                else:
                    response.data['friendship_status'] = 'none'
            except (ValueError, Friend.DoesNotExist):
                response.data['friendship_status'] = 'none'     
        return response

class UserUpdateAPIView(UpdateAPIView):
    serializer_class = UserUpdateSerializer

    def get_object(self):
        return self.request.user

    def put(self, request, *args, **kwargs):
        return Response(
            {'error': 'PUT method is not allowed. Use PATCH instead.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def patch(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', True)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response({
            "username": instance.username,
            "avatar": instance.avatar
        }, status=status.HTTP_200_OK)


# TODO: doesn't work yet
class UserStatsAPIView(RetrieveAPIView):
    queryset = UserStats.objects.all()
    serializer_class = UserStatsSerializer
    permission_classes = [permissions.AllowAny]

    def get_object(self):
        user_id = self.kwargs.get('user_id', None)
        if user_id:
            user = User.objects.get(id=user_id)
            return user.stats
        return self.request.user.stats

# TODO: more tests needed
class FriendListAPIView(ListAPIView):
    serializer_class = FriendSerializer

    def get_queryset(self):
        user = self.request.user
        return Friend.objects.filter(user=user)

# TODO: more tests needed
class FriendshipAPIView(APIView):
    """
    API for managing friend requests and friendship statuses.
    """
    def post(self, request, *args, **kwargs):
        """
        Send a friend request.
        """
        user = request.user
        friend_id = request.data.get('friend_id')

        if not friend_id:
            return Response({'error': 'Friend ID is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            friend = User.objects.get(id=friend_id)
        except User.DoesNotExist:
            return Response({'error': 'Friend not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Try to create a friend request
        if user == friend:
            return Response({'error': 'You cannot add yourself as a friend.'}, status=status.HTTP_400_BAD_REQUEST)

        friendship, created = Friend.add_friend(user, friend)
        if not created:
            return Response({'message': 'Friendship already exists or is pending.'}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'message': 'Friendship request sent.'}, status=status.HTTP_201_CREATED)

    def delete(self, request, *args, **kwargs):
        """
        Delete a friend or cancel a friend request.
        """
        user = request.user
        friend_id = request.data.get('friend_id')

        if not friend_id:
            return Response({'error': 'Friend ID is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            friend = User.objects.get(id=friend_id)
        except User.DoesNotExist:
            return Response({'error': 'Friend not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Try to delete the friendship
        try:
            friendship = Friend.objects.get(user=user, friend=friend)
            friendship.delete()
            return Response({'message': 'Friendship deleted.'}, status=status.HTTP_204_NO_CONTENT)
        except Friend.DoesNotExist:
            return Response({'error': 'Friendship does not exist.'}, status=status.HTTP_400_BAD_REQUEST)
    
    def patch(self, request, *args, **kwargs):
        """
        Accept or decline a friend request.
        """
        user = request.user
        friend_id = request.data.get('friend_id')
        action = request.data.get('action')  # 'accept' or 'decline'

        if not friend_id or not action:
            return Response({'error': 'Friend ID and action are required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            friend = User.objects.get(id=friend_id)
        except User.DoesNotExist:
            return Response({'error': 'Friend not found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            friendship = Friend.objects.get(user=friend, friend=user, status='pending')
        except Friend.DoesNotExist:
            return Response({'error': 'Friendship request not found.'}, status=status.HTTP_404_NOT_FOUND)

        if action == 'accept':
            friendship.accept_friend()
            return Response({'message': 'Friendship request accepted.'}, status=status.HTTP_200_OK)
        elif action == 'decline':
            friendship.decline_friend()
            return Response({'message': 'Friendship request declined.'}, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'Invalid action.'}, status=status.HTTP_400_BAD_REQUEST)