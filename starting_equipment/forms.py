"""Forms for starting equipment templates."""

from django import forms

from starting_equipment.models import StartingEquipmentTemplate


class TemplateForm(forms.ModelForm):
    """Form for creating and editing StartingEquipmentTemplate."""

    class Meta:
        model = StartingEquipmentTemplate
        fields = ["name", "description", "is_active"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, club, **kwargs):
        super().__init__(*args, **kwargs)
        self.club = club
        self.fields["name"].help_text = "Unique within this club."
        self.fields["description"].help_text = "Optional description of this template."
        self.fields[
            "is_active"
        ].help_text = (
            "Only one template can be active per club. Activating this will deactivate others."
        )

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        clash = (
            StartingEquipmentTemplate.objects.for_club(self.club)
            .filter(name__iexact=name)
            .exclude(pk=self.instance.pk)
            .exists()
        )
        if clash:
            raise forms.ValidationError("A template with this name already exists in this club.")
        return name

    def save(self, commit=True):
        self.instance.club = self.club
        return super().save(commit=commit)
