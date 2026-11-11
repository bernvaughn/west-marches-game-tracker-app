from django import forms

from player_characters.models import Character

from ..models import Message


class MessageForm(forms.ModelForm):
    body = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={"rows": 4}))

    class Meta:
        model = Message
        fields = ["body", "character"]

    def __init__(self, *args, membership, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["character"].queryset = Character.objects.for_club(membership.club).filter(
            owner=membership
        )
        self.fields["character"].required = False


class StatusForm(forms.Form):
    status = forms.ChoiceField(choices=Message.Status.choices)
