from django import forms

from ..models import Message

# Quick templates for the "Message the admins" form (Message.Kind.MESSAGE only).
# {character} is replaced with the sender's selected character name.
TEMPLATE_CHOICES = [
    ("loot", "Loot correction"),
    ("map", "Map credit"),
    ("shop", "Shop stock request"),
    ("other", "Other"),
]

TEMPLATE_TEXTS = {
    "loot": "I think {character} is missing: [items/coins] from the last session. Details: ",
    "map": "Please mark {character} as having visited/found: [location/tile]. Details: ",
    "shop": "Could [shop] start carrying [item]? Details: ",
    "other": "",
}


class MessageForm(forms.ModelForm):
    body = forms.CharField(
        label="Message", max_length=2000, widget=forms.Textarea(attrs={"rows": 4})
    )
    template = forms.ChoiceField(choices=TEMPLATE_CHOICES, required=False)

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


class BulkStatusForm(forms.Form):
    message_ids = forms.ModelMultipleChoiceField(
        queryset=Message.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=True,
    )
    status = forms.ChoiceField(choices=Message.Status.choices)

    def __init__(self, *args, club=None, **kwargs):
        super().__init__(*args, **kwargs)
        if club is not None:
            self.fields["message_ids"].queryset = Message.objects.for_club(club)


STATUS_ACTIONS = {"handled": "Mark handled", "closed": "Close", "open": "Reopen"}


def allowed_statuses(msg):
    """The status buttons that apply to a message."""
    if msg.status == Message.Status.OPEN:
        return ("handled", "closed")
    return ("open",)
