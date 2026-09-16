from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import APIException
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.activity_log.models import ActivityLog
from apps.activity_log.services import log_activity
from apps.notifications.models import Notification
from apps.notifications.services import notify, notify_admins
from common.emails import send_client_welcome_email
from common.permissions import IsAdmin

from .models import LoginHistory, User
from .serializers import (
    AdminUserUpdateSerializer,
    ChangePasswordSerializer,
    CreateUserSerializer,
    CustomTokenObtainPairSerializer,
    ForgotPasswordSerializer,
    LoginHistorySerializer,
    ProfileUpdateSerializer,
    RefreshTokenSerializer,
    ResetPasswordSerializer,
    UserSerializer,
    build_uid_and_token,
)


def _client_ip(request):
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


# Epic 24 (Security: Suspicious activity) - past this many failed attempts for the
# same email within the window, further attempts are blocked outright rather than
# left to ScopedRateThrottle alone, which only limits *frequency* and would still
# let a slow, patient brute force through indefinitely.
LOGIN_LOCKOUT_THRESHOLD = 5
LOGIN_LOCKOUT_WINDOW_MINUTES = 15


class LoginView(TokenObtainPairView):
    """Authenticates a user with email/password and returns a JWT pair.

    Records every attempt (success or failure) to LoginHistory per
    Epic 01 (Login history) / Epic 24 (Login monitoring), and temporarily locks
    out an email after repeated failures (Epic 24: Suspicious activity).
    """

    serializer_class = CustomTokenObtainPairSerializer
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'

    def post(self, request, *args, **kwargs):
        email = request.data.get('email', '')
        ip_address = _client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:255]

        window_start = timezone.now() - timezone.timedelta(minutes=LOGIN_LOCKOUT_WINDOW_MINUTES)
        recent_failures = LoginHistory.objects.filter(
            email_attempted__iexact=email, was_successful=False, created_at__gte=window_start,
        ).count()

        if recent_failures >= LOGIN_LOCKOUT_THRESHOLD:
            log_activity(
                module=ActivityLog.Module.AUTH, action='Login blocked (too many failed attempts)',
                description=email, request=request,
            )
            return Response(
                {'detail': 'Too many failed login attempts. Try again in a few minutes.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        try:
            response = super().post(request, *args, **kwargs)
        except APIException:
            LoginHistory.objects.create(
                user=User.objects.filter(email__iexact=email).first(),
                email_attempted=email,
                ip_address=ip_address,
                user_agent=user_agent,
                was_successful=False,
            )
            if recent_failures + 1 == LOGIN_LOCKOUT_THRESHOLD:
                # Notify only on the attempt that crosses the threshold, not on
                # every one of the (now-blocked) attempts after it - otherwise an
                # attacker retrying every few seconds would flood every admin.
                notify_admins(
                    actor=None,
                    notification_type=Notification.NotificationType.SUSPICIOUS_LOGIN,
                    title=f'Repeated failed logins for {email}',
                    message=(
                        f'{LOGIN_LOCKOUT_THRESHOLD} failed attempts in the last '
                        f'{LOGIN_LOCKOUT_WINDOW_MINUTES} minutes from IP {ip_address}. This email is now '
                        f'temporarily locked out.'
                    ),
                    url='/activity-log',
                )
            raise

        logged_in_user = User.objects.filter(email__iexact=email).first()
        LoginHistory.objects.create(
            user=logged_in_user,
            email_attempted=email,
            ip_address=ip_address,
            user_agent=user_agent,
            was_successful=True,
        )
        log_activity(
            module=ActivityLog.Module.AUTH, action='Logged in', user=logged_in_user, request=request,
        )
        return response


class LogoutView(APIView):
    """Blacklists the given refresh token, ending the session."""

    permission_classes = [IsAuthenticated]
    serializer_class = RefreshTokenSerializer

    def post(self, request):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response({'detail': 'refresh token is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError:
            return Response({'detail': 'Invalid or already blacklisted token.'}, status=status.HTTP_400_BAD_REQUEST)
        log_activity(module=ActivityLog.Module.AUTH, action='Logged out', request=request)
        return Response(status=status.HTTP_205_RESET_CONTENT)


class ProfileView(generics.RetrieveUpdateAPIView):
    """The authenticated user's own profile (Epic 20: Client settings / profile)."""

    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return ProfileUpdateSerializer
        return UserSerializer


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ChangePasswordSerializer

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        log_activity(module=ActivityLog.Module.SETTINGS, action='Password changed', request=request)
        return Response({'detail': 'Password changed successfully.'})


class ForgotPasswordView(APIView):
    """Issues a password reset link and emails it to the user, if the account exists.

    Always returns 200 with a generic message so the endpoint cannot be used
    to enumerate registered email addresses.
    """

    permission_classes = [AllowAny]
    serializer_class = ForgotPasswordSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'password_reset'

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.get_user()

        if user is not None:
            uid, token = build_uid_and_token(user)
            reset_link = f'{settings.FRONTEND_URL.rstrip("/")}/reset-password?uid={uid}&token={token}'
            send_mail(
                subject='Reset your password',
                message=f'Use the link below to reset your password:\n\n{reset_link}\n\n'
                        'If you did not request this, you can ignore this email.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,
            )

        return Response({'detail': 'If an account exists for that email, a reset link has been sent.'})


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]
    serializer_class = ResetPasswordSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'password_reset'

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        log_activity(
            module=ActivityLog.Module.SETTINGS, action='Password reset via email link',
            user=serializer.validated_data['user'], request=request,
        )
        return Response({'detail': 'Password has been reset successfully.'})


class MyLoginHistoryView(generics.ListAPIView):
    """The authenticated user's own login history."""

    serializer_class = LoginHistorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return LoginHistory.objects.filter(user=self.request.user)


class UserListCreateView(generics.ListCreateAPIView):
    """Admin: list all users, or create a new Client or Admin login (Epic 01/02/24)."""

    permission_classes = [IsAdmin]
    queryset = User.objects.all()

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CreateUserSerializer
        return UserSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        role = self.request.query_params.get('role')
        if role:
            queryset = queryset.filter(role=role)
        return queryset

    def perform_create(self, serializer):
        serializer.save()
        new_user = serializer.instance
        plain_password = serializer._plain_password  # noqa: SLF001 - only known right after creation
        if plain_password:
            send_client_welcome_email(new_user, plain_password)

        log_activity(
            module=ActivityLog.Module.AUTH,
            action=f'{new_user.get_role_display()} created',
            description=new_user.email,
            request=self.request,
        )

        if new_user.is_admin:
            notify_admins(
                actor=self.request.user,
                notification_type=Notification.NotificationType.ADMIN_ADDED,
                title=f'{new_user.get_short_name()} joined as an admin',
                message=f'Added by {self.request.user.get_short_name()}.',
                url='/team',
            )
            notify(
                new_user,
                Notification.NotificationType.ADMIN_ADDED,
                title='You were added as an admin',
                message='You now have full access to the platform.',
                url='/team',
            )


class UserDetailView(generics.RetrieveUpdateAPIView):
    """Admin: view or edit a user, including activating/deactivating them."""

    permission_classes = [IsAdmin]
    queryset = User.objects.all()

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return AdminUserUpdateSerializer
        return UserSerializer

    def update(self, request, *args, **kwargs):
        """Validates/saves via AdminUserUpdateSerializer (writable fields only), but
        always responds with the full UserSerializer representation - callers that merge
        this response into local state (TeamPage, AccessControlPage) need `id`/`email`/
        `full_name` to still be there for a second edit, and AdminUserUpdateSerializer
        deliberately omits them since they're not writable.
        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        was_active = instance.is_active
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        if instance.is_active != was_active:
            log_activity(
                module=ActivityLog.Module.AUTH,
                action='User activated' if instance.is_active else 'User deactivated',
                description=instance.email,
                request=request,
            )
        return Response(UserSerializer(instance).data)


class UserLoginHistoryView(generics.ListAPIView):
    """Admin: view a specific user's login history."""

    serializer_class = LoginHistorySerializer
    permission_classes = [IsAdmin]

    def get_queryset(self):
        return LoginHistory.objects.filter(user_id=self.kwargs['pk'])
