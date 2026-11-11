from django.contrib import admin

from .models import AgentConnection, ProposedBatch, ProposedItem, ProposedLine

admin.site.register([AgentConnection, ProposedBatch, ProposedItem, ProposedLine])
