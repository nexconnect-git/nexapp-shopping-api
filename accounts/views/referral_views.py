"""Referral program views."""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny

from accounts.models.referral import ReferralCode, Referral, REFERRAL_BONUS_POINTS


class MyReferralView(APIView):
    """GET /api/auth/referral/ — return the caller's referral code and stats."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        ref_code = ReferralCode.get_or_create_for_user(request.user)
        referrals = Referral.objects.filter(referrer=request.user).select_related('referee')
        referee_list = [
            {
                'name': f"{r.referee.first_name} {r.referee.last_name}".strip() or r.referee.username,
                'joined_at': r.created_at.isoformat(),
                'bonus_awarded': r.bonus_awarded,
            }
            for r in referrals
        ]
        return Response({
            'code': ref_code.code,
            'total_referrals': len(referee_list),
            'bonus_per_referral': REFERRAL_BONUS_POINTS,
            'referrals': referee_list,
        })


class ApplyReferralCodeView(APIView):
    """POST /api/auth/referral/apply/ — apply a referral code after registration.

    Body: { "code": "ABCD1234" }
    Returns 200 if code is valid and applied, 400 otherwise.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        code = request.data.get('code', '').strip().upper()
        if not code:
            return Response({'error': 'Referral code is required.'}, status=400)

        # Prevent self-referral
        try:
            ref_code_obj = ReferralCode.objects.get(code=code)
        except ReferralCode.DoesNotExist:
            return Response({'error': 'Invalid referral code.'}, status=400)

        if ref_code_obj.user == request.user:
            return Response({'error': 'You cannot use your own referral code.'}, status=400)

        # Check if user already has a referral record
        if Referral.objects.filter(referee=request.user).exists():
            return Response({'error': 'You have already applied a referral code.'}, status=400)

        Referral.objects.create(referrer=ref_code_obj.user, referee=request.user)
        return Response({'message': 'Referral code applied! Bonus points will be awarded after your first order.'})


class ReferralCodeLookupView(APIView):
    """GET /api/auth/referral/lookup/?code=XXX — validate a referral code (public)."""

    permission_classes = [AllowAny]

    def get(self, request):
        code = request.query_params.get('code', '').strip().upper()
        if not code:
            return Response({'valid': False})
        exists = ReferralCode.objects.filter(code=code).exists()
        return Response({'valid': exists, 'code': code if exists else ''})
