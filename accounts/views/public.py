from django.shortcuts import render

from config import plans as plan_config


def about(request):
    return render(request, "public/about.html")


def plans(request):
    return render(request, "public/plans.html", {"plans": plan_config.PLANS})
