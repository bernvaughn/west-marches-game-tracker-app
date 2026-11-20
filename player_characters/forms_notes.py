from django import forms

from .notes import NOTE_MAX


class NoteForm(forms.Form):
    """One text box for a player's note on an item.

    Browsers send newlines as `\r\n`, which Django counts as two characters.
    Normalise to `\n` in `clean_text` before the length check so a 1,000
    character note with newlines is accepted.
    """

    text = forms.CharField(
        required=False,
        strip=True,
        label="Your note",
        widget=forms.Textarea(attrs={"rows": 5, "maxlength": 1000}),
    )

    def clean_text(self):
        text = self.cleaned_data.get("text", "")
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        if len(text) > NOTE_MAX:
            raise forms.ValidationError(f"Notes can be at most {NOTE_MAX} characters.")
        return text
