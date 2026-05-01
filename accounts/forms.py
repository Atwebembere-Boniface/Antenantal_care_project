from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.contrib.auth import get_user_model
from .models import PatientProfile, StaffProfile

# Use get_user_model() to avoid "already registered" warnings
User = get_user_model()

class StaffSignUpForm(UserCreationForm):
    role = forms.ChoiceField(choices=[('DOCTOR', 'Doctor'), ('NURSE', 'Nurse')], required=True)
    employee_id = forms.CharField(max_length=20, required=True)
    phone_number = forms.CharField(max_length=15, required=True)
    
    # NEW: Security field for staff authorization
    registration_code = forms.CharField(
        max_length=4, 
        label="Staff Authorization Code",
        help_text="Enter the 4-digit departmental code to verify registration.",
        widget=forms.PasswordInput(attrs={'placeholder': '••••'}) 
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "phone_number")

    def clean_registration_code(self):
        """Verify that the user knows the departmental security code."""
        code = self.cleaned_data.get('registration_code')
        if code != "2026":
            raise forms.ValidationError("Invalid Authorization Code. Please contact the administrator.")
        return code

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = self.cleaned_data.get('role')
        user.phone_number = self.cleaned_data.get('phone_number')
        if commit:
            user.save()
            StaffProfile.objects.update_or_create(
                user=user,
                defaults={'employee_id': self.cleaned_data.get('employee_id')}
            )
        return user


class PatientRegistrationForm(forms.ModelForm):
    phone_number = forms.CharField(
        max_length=15,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone Number'})
    )
    
    full_name = forms.CharField(
        max_length=255, required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First and Last Name'})
    )
    pregnancy_period = forms.IntegerField(
        label="Pregnancy Period (Weeks)", required=True,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 40})
    )
    address = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}), required=True
    )
    age = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    assigned_doctor = forms.ModelChoiceField(
        queryset=User.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = User
        fields = ("email",) 
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            self.fields['assigned_doctor'].queryset = User.objects.filter(role='DOCTOR')
        except Exception:
            self.fields['assigned_doctor'].queryset = User.objects.none()

    def save(self, commit=True):
        user = super().save(commit=False)
        
        full_name = self.cleaned_data.get('full_name', '')
        name_parts = full_name.split(' ', 1)
        user.first_name = name_parts[0]
        user.last_name = name_parts[1] if len(name_parts) > 1 else ""
        
        phone = self.cleaned_data.get('phone_number')
        user.phone_number = phone 
        user.username = phone
        user.role = 'PATIENT'
        user.set_password(phone)
        user.must_change_password = True
        
        if commit:
            user.save()
            PatientProfile.objects.update_or_create(
                user=user,
                defaults={
                    'address': self.cleaned_data.get('address'),
                    'pregnancy_period': self.cleaned_data.get('pregnancy_period'),
                    'age': self.cleaned_data.get('age'),
                    'assigned_doctor': self.cleaned_data.get('assigned_doctor'),
                }
            )
        return user

class ForcePasswordChangeForm(PasswordChangeForm):
    new_username = forms.CharField(
        max_length=150, required=True, label="New Username",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Choose a username'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if not hasattr(field.widget, 'attrs'):
                field.widget.attrs = {}
            field.widget.attrs['class'] = 'form-control'