# core/views_payments.py — NEW FILE, add it alongside your existing views.py
#
# pip install razorpay
#
# settings.py additions:
#   RAZORPAY_KEY_ID = env("RAZORPAY_KEY_ID")
#   RAZORPAY_KEY_SECRET = env("RAZORPAY_KEY_SECRET")
#   RAZORPAY_WEBHOOK_SECRET = env("RAZORPAY_WEBHOOK_SECRET")
#
# Get keys from the Razorpay dashboard. Start in TEST MODE and only switch
# to live keys once a full buy -> verify -> unlock cycle works end to end.
#
# Webhook setup (recommended safety net): Razorpay dashboard -> Settings ->
# Webhooks -> add https://yourdomain.com/payments/webhook/ -> subscribe to
# "payment.captured" -> copy the generated secret into RAZORPAY_WEBHOOK_SECRET.
# This catches the case where a buyer pays successfully but closes the tab
# before the browser-side verify call fires.

import json

import razorpay
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import Content, Subject, SubscriptionPlan, Purchase

client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


@login_required
@require_http_methods(["POST"])
def create_order_view(request):
    """
    Called by the 'Buy' button on the public content/course page.
    Body (JSON): { "purchase_type": "content"|"subject"|"plan", "object_id": <id> }

    @login_required is what actually enforces "must be logged in to buy" —
    an anonymous POST here 302s to /login/?next=..., matching the flow
    from the public content page.
    """
    try:
        payload = json.loads(request.body)
        purchase_type = payload["purchase_type"]
        object_id = payload["object_id"]
    except (KeyError, ValueError, TypeError):
        return HttpResponseBadRequest("Malformed request")

    if purchase_type == "content":
        obj = get_object_or_404(Content, id=object_id)
        if not obj.price:
            return HttpResponseBadRequest("This chapter isn't sold individually")
        amount = obj.price
        kwargs = {"content": obj}
        description = f"{obj.subject.name} — {obj.title}"
    elif purchase_type == "subject":
        obj = get_object_or_404(Subject, id=object_id)
        if not obj.price:
            return HttpResponseBadRequest("This course isn't sold as a bundle")
        amount = obj.price
        kwargs = {"subject": obj}
        description = f"{obj.name} (full course)"
    elif purchase_type == "plan":
        obj = get_object_or_404(SubscriptionPlan, id=object_id, is_active=True)
        amount = obj.price
        kwargs = {"plan": obj}
        description = obj.name
    else:
        return HttpResponseBadRequest("Unknown purchase_type")

    amount_paise = int(amount * 100)

    razorpay_order = client.order.create({
        "amount": amount_paise,
        "currency": "INR",
        "payment_capture": 1,
    })

    purchase = Purchase.objects.create(
        user=request.user,
        purchase_type=purchase_type,
        amount=amount,
        status="created",
        razorpay_order_id=razorpay_order["id"],
        **kwargs,
    )

    return JsonResponse({
        "key": settings.RAZORPAY_KEY_ID,
        "order_id": razorpay_order["id"],
        "amount": amount_paise,
        "currency": "INR",
        "purchase_id": purchase.id,
        "name": "StudyPalz",
        "description": description,
        "prefill": {"email": request.user.email, "name": request.user.first_name},
    })


@login_required
@require_http_methods(["POST"])
def verify_payment_view(request):
    """
    Called by Razorpay Checkout.js's success handler right after payment.
    Confirms the signature server-side before unlocking anything — never
    trust the client's word that payment succeeded.
    """
    try:
        payload = json.loads(request.body)
        order_id = payload["razorpay_order_id"]
        payment_id = payload["razorpay_payment_id"]
        signature = payload["razorpay_signature"]
    except (KeyError, ValueError, TypeError):
        return HttpResponseBadRequest("Malformed request")

    purchase = get_object_or_404(Purchase, razorpay_order_id=order_id, user=request.user)

    try:
        client.utility.verify_payment_signature({
            "razorpay_order_id": order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": signature,
        })
    except razorpay.errors.SignatureVerificationError:
        purchase.status = "failed"
        purchase.save(update_fields=["status"])
        return JsonResponse({"status": "failed"}, status=400)

    purchase.mark_paid(payment_id, signature)
    return JsonResponse({"status": "paid"})


@csrf_exempt
@require_http_methods(["POST"])
def razorpay_webhook_view(request):
    """
    Server-to-server safety net — see setup notes at the top of this file.
    Idempotent: safe to receive the same event more than once.
    """
    signature = request.headers.get("X-Razorpay-Signature", "")
    body = request.body

    try:
        client.utility.verify_webhook_signature(
            body.decode("utf-8"), signature, settings.RAZORPAY_WEBHOOK_SECRET
        )
    except razorpay.errors.SignatureVerificationError:
        return HttpResponseBadRequest("Invalid signature")

    event = json.loads(body)

    if event.get("event") == "payment.captured":
        payment_entity = event["payload"]["payment"]["entity"]
        order_id = payment_entity["order_id"]
        payment_id = payment_entity["id"]

        purchase = Purchase.objects.filter(razorpay_order_id=order_id).first()
        if purchase and purchase.status != "paid":
            purchase.mark_paid(payment_id, signature="webhook-verified")

    return JsonResponse({"status": "ok"})
