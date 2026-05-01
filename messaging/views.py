from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.db.models import Q
from accounts.models import User
from .models import Message

def get_display_name(user):
    """Return full name if available, otherwise fall back to username."""
    full_name = user.get_full_name().strip()
    return full_name if full_name else user.username

class InboxView(LoginRequiredMixin, View):
    template_name = 'messaging/inbox.html'

    def get(self, request):
        user = request.user
        sent_to = Message.objects.filter(sender=user).values_list('recipient_id', flat=True)
        received_from = Message.objects.filter(recipient=user).values_list('sender_id', flat=True)
        partner_ids = set(list(sent_to) + list(received_from))

        conversations = []
        for pid in partner_ids:
            try:
                partner = User.objects.get(id=pid)
                partner.display_name = get_display_name(partner)
                last_msg = Message.objects.filter(
                    Q(sender=user, recipient=partner) | Q(sender=partner, recipient=user)
                ).order_by('-created_at').first()
                unread = Message.objects.filter(sender=partner, recipient=user, is_read=False).count()
                conversations.append({
                    'partner': partner,
                    'last_message': last_msg,
                    'unread': unread,
                })
            except User.DoesNotExist:
                continue

        conversations.sort(
            key=lambda c: c['last_message'].created_at if c['last_message'] else 0,
            reverse=True
        )

        if user.role == 'PATIENT':
            contacts = User.objects.filter(role__in=['DOCTOR', 'NURSE']).order_by('last_name', 'username')
        elif user.role in ['DOCTOR', 'NURSE']:
            from accounts.models import PatientProfile
            patient_user_ids = PatientProfile.objects.filter(assigned_doctor=user).values_list('user_id', flat=True)
            contacts = User.objects.filter(id__in=patient_user_ids).order_by('last_name', 'username')
        else:
            contacts = User.objects.exclude(id=user.id).order_by('role', 'last_name', 'username')

        for contact in contacts:
            contact.display_name = get_display_name(contact)

        return render(request, self.template_name, {
            'conversations': conversations,
            'contacts': contacts,
        })

class ConversationView(LoginRequiredMixin, View):
    # FIXED: Updated path to match the actual file location
    template_name = 'messaging/conversation.html' 

    def get(self, request, user_id):
        partner = get_object_or_404(User, id=user_id)
        partner.display_name = get_display_name(partner)

        messages_qs = Message.objects.filter(
            Q(sender=request.user, recipient=partner) |
            Q(sender=partner, recipient=request.user)
        ).order_by('created_at')

        messages_qs.filter(recipient=request.user, is_read=False).update(is_read=True)

        return render(request, self.template_name, {
            'partner': partner,
            'messages': messages_qs,
        })

    def post(self, request, user_id):
        partner = get_object_or_404(User, id=user_id)
        body = request.POST.get('body', '').strip()
        if body:
            Message.objects.create(sender=request.user, recipient=partner, body=body)
        
        return redirect('messaging:conversation', user_id=user_id)

class SendMessageView(LoginRequiredMixin, View):
    def post(self, request):
        recipient_id = request.POST.get('recipient_id')
        body = request.POST.get('body', '').strip()
        recipient = get_object_or_404(User, id=recipient_id)
        if body:
            Message.objects.create(sender=request.user, recipient=recipient, body=body)
        
        return redirect('messaging:conversation', user_id=recipient_id)