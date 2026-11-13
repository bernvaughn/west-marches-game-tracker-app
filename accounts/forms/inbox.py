from django import forms

from ..models import Message


class MessageForm(forms.ModelForm):
    body = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={"rows": 4}))

    class Meta:
        model = Message
        fields = ["body"]


class StockRequestForm(MessageForm):
    body = forms.CharField(
        label="Request",
        max_length=2000,
        widget=forms.Textarea(
            attrs={"rows": 4, "placeholder": "I want to be able to buy some super cool armor!"}
        ),
    )


class StatusForm(forms.Form):
    status = forms.ChoiceField(choices=Message.Status.choices)


STATUS_ACTIONS = {"handled": "Mark handled", "closed": "Close", "open": "Reopen"}


def allowed_statuses(msg):
    """The status buttons that apply to a message."""
    if msg.status == Message.Status.OPEN:
        return ("handled", "closed")
    return ("open",)
