# Python challenge Project

# Configure Local Development Environment
## Requirements
1. Python 3.11
2. Docker
3. Minikube (make sure, that your minikube client is running)
4. Helm
5. Windows OS

## Steps
1.Builds, (re)creates, starts, and attaches to containers for a service: 
```bash
docker-compose up -d --build
```

2.Launch migrations:
```bash
docker-compose exec web python manage.py migrate --noinput
```

3.Create admin user:
```bash
docker-compose exec web python manage.py createsuperuser
```
After all manipulations you can access admin panel by link:
```bash 
http://127.0.0.1:8000/admin
```
Phase 1:
Apply CRD named Application:
```bash 
kubectl apply -f my-k8s-operator/crds/django-crd.yaml
```
Check, that CRD correctly installed:
```bash 
kubectl get crds
```

Phase 2:
In this phase I created deployment_operator.py file with three methods:
- create_application (сonsist deployment and service creation logic)
- update_application (сonsist deployment and service update logic)
- delete_application (сonsist deployment and service deletion logic)

Phase 3:
In this phase I updated main crd file, where added cpu_threshold and memory_threshold specs
In next step I updated such method:
- create_application (added HPA creation with cpu_threshold and memory_threshold params)
- update_application (added HPA update with cpu_threshold and memory_threshold params)
- delete_application (added HPA update deletion logic)
To see simulating CPU or memory load, at first we will create django-application.yaml and django-hpa.yaml files and we will execute next commands:
```bash 
kubectl apply -f my-k8s-operator/django-application.yaml
```
```bash 
kubectl apply -f my-k8s-operator/django-hpa.yaml
```
After that, we can execute two commands for check simulating CPU or memory load:
```bash 
kubectl get hpa
```
```bash 
kubectl get pods
```

Phase 4:
At first, in this phase, I created new chart with Helm base files. 
I deleted all templates files, move crd file to crds folder, and created in templates folder such files:
- django-deployment.yaml (Operator Deployment)
- django-role.yaml (Role)
- django-rolebinding.yaml (RoleBindings)
- django-service-account.yaml (Service Account)

In next step I deployed my operator through next command:
```bash 
helm install my-operator ./my-k8s-operator
```
Phase 5:
In this phase I updated main crd file, where added monitoring spec
In python file deployment_operator I added two functions:
- create_servicemonitor (called in create_application, if monitoring spec is set to True)
- delete_servicemonitor (called in delete_application, when deletion application happens)
If you want to see create_application execution time, just use next command:
```bash 
python deployment_operator.py
```
Next, in browser, through localhost:8000, at the very bottom, you can see request_processing_seconds_created
param, that display execution time

When finishes your test, you can stop and remove all containers by command:
```bash
docker-compose down
```
Also, we will clear all configuration files and heml chart:
```bash
kubectl delete -f my-k8s-operator/crds/django-crd.yaml
```
```bash
kubectl delete -f my-k8s-operator/django-application.yaml
```
```bash 
kubectl delete -f my-k8s-operator/django-hpa.yaml
```
```bash
helm delete my-operator  
```
