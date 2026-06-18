import base64
from io import BytesIO

import qrcode
import qrcode.constants
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.data.order_repo import OrderRepository
from orders.models import Order
from orders.models.setting import PlatformSetting


class OrderPaymentQRView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            order = OrderRepository.get_by_id(pk)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)

        if order.delivery_partner != request.user and order.customer != request.user:
            return Response({'error': 'Access denied.'}, status=status.HTTP_403_FORBIDDEN)

        amount = str(order.total)
        setting = PlatformSetting.get_setting()
        manual_qr = (setting.cod_payment_qr or '').strip()
        upi_string = f'upi://pay?pa={setting.upi_id}&pn=Nextou&am={amount}&cu=INR&tn=Order%20{order.order_number}'
        if manual_qr:
            return Response({
                'order_number': order.order_number,
                'amount': amount,
                'qr_base64': manual_qr,
                'upi_string': upi_string,
                'source': 'admin',
            })

        qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M)
        qr.add_data(upi_string)
        qr.make(fit=True)
        qr_image = qr.make_image(fill_color='black', back_color='white')

        qr_buffer = BytesIO()
        qr_image.save(qr_buffer, format='PNG')
        qr_base64_string = base64.b64encode(qr_buffer.getvalue()).decode('utf-8')

        return Response({
            'order_number': order.order_number,
            'amount': amount,
            'qr_base64': f'data:image/png;base64,{qr_base64_string}',
            'upi_string': upi_string,
            'source': 'generated',
        })
