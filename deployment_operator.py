import kopf
import logging
from kubernetes import client, config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load the Kubernetes configuration
# config.load_incluster_config()  # Use if running inside a pod
config.load_kube_config()      # Uncomment for local development


def create_servicemonitor(name, namespace, port, logger):
    sm = {
        "apiVersion": "monitoring.coreos.com/v1",
        "kind": "ServiceMonitor",
        "metadata": {
            "name": f"{name}-monitor",
            "namespace": namespace,
            "labels": {
                "app": name
            }
        },
        "spec": {
            "selector": {
                "matchLabels": {
                    "app": name
                }
            },
            "endpoints": [
                {
                    "port": "http",  # Ensure this matches your service port
                    "interval": "30s"
                }
            ]
        }
    }
    api = client.CustomObjectsApi()
    try:
        api.create_namespaced_custom_object(
            group="monitoring.coreos.com",
            version="v1",
            namespace=namespace,
            plural="servicemonitors",
            body=sm
        )
        logger.info(f"Created ServiceMonitor {name}-monitor in {namespace}.")
    except Exception as e:
        logger.error(f"Failed to create ServiceMonitor: {e}")


@kopf.on.create('mydomain.com', 'v1', 'applications')
def create_application(spec, name, namespace, **kwargs):
    try:
        replicas = spec.get('replicas', 1)
        image = spec.get('image')
        port = spec.get('port', 80)
        cpu_threshold = spec.get('cpu_threshold')
        memory_threshold = spec.get('memory_threshold')
        monitoring = spec.get('monitoring')

        # Create Deployment
        apps_v1 = client.AppsV1Api()
        deployment = client.V1Deployment(
            api_version='apps/v1',
            kind='Deployment',
            metadata=client.V1ObjectMeta(name=name, namespace=namespace),
            spec=client.V1DeploymentSpec(
                replicas=replicas,
                selector={'matchLabels': {'app': name}},
                template=client.V1PodTemplateSpec(
                    metadata=client.V1ObjectMeta(labels={'app': name}),
                    spec=client.V1PodSpec(
                        containers=[client.V1Container(name=name, image=image, ports=[client.V1ContainerPort(container_port=port)])]
                    )
                )
            )
        )
        apps_v1.create_namespaced_deployment(namespace=namespace, body=deployment)
        logger.info(f"Created Deployment {name} in {namespace}")

        # Create Service
        core_v1 = client.CoreV1Api()
        service = client.V1Service(
            api_version='v1',
            kind='Service',
            metadata=client.V1ObjectMeta(name=name, namespace=namespace),
            spec=client.V1ServiceSpec(
                selector={'app': name},
                ports=[client.V1ServicePort(port=port, target_port=port)],
                type='ClusterIP'  # Change to 'NodePort' if you want external access
            )
        )
        core_v1.create_namespaced_service(namespace=namespace, body=service)
        logger.info(f"Created Service {name} in {namespace}")

        # Create HPA if thresholds are specified
        if cpu_threshold or memory_threshold:
            hpa = client.V2HorizontalPodAutoscaler(
                api_version='autoscaling/v2beta2',
                kind='HorizontalPodAutoscaler',
                metadata=client.V1ObjectMeta(name=name, namespace=namespace),
                spec=client.V2HorizontalPodAutoscalerSpec(
                    scale_target_ref=client.V2CrossVersionObjectReference(
                        api_version='apps/v1',
                        kind='Deployment',
                        name=name
                    ),
                    min_replicas=1,
                    max_replicas=10,
                    metrics=[]
                )
            )

            if cpu_threshold:
                hpa.spec.metrics.append(client.V2MetricSpec(
                    type='Resource',
                    resource=client.V2ResourceMetricSource(
                        name='cpu',
                        target=client.V2MetricTarget(
                            type='Utilization',
                            average_utilization=int(cpu_threshold[:-1])  # Remove 'm' and convert to int
                        )
                    )
                ))

            if memory_threshold:
                hpa.spec.metrics.append(client.V2MetricSpec(
                    type='Resource',
                    resource=client.V2ResourceMetricSource(
                        name='memory',
                        target=client.V2MetricTarget(
                            type='Utilization',
                            average_utilization=int(memory_threshold[:-2])  # Remove 'Mi' and convert to int
                        )
                    )
                ))

            autoscaling_v1 = client.AutoscalingV1Api()
            autoscaling_v1.create_namespaced_horizontal_pod_autoscaler(namespace=namespace, body=hpa)
            logger.info(f"Created HPA {name} in {namespace}")

        if monitoring:
            create_servicemonitor(name, namespace, spec['port'], logger)

    except Exception as e:
        logger.error(f"Error creating application {name} in {namespace}: {e}")


@kopf.on.update('mydomain.com', 'v1', 'applications')
def update_application(spec, name, namespace, **kwargs):
    try:
        replicas = spec.get('replicas')
        image = spec.get('image')
        port = spec.get('port')
        cpu_threshold = spec.get('cpu_threshold')
        memory_threshold = spec.get('memory_threshold')

        apps_v1 = client.AppsV1Api()

        # Update Deployment
        deployment = apps_v1.read_namespaced_deployment(name, namespace)
        if replicas is not None:
            deployment.spec.replicas = replicas
        if image is not None:
            deployment.spec.template.spec.containers[0].image = image
        if port is not None:
            deployment.spec.template.spec.containers[0].ports[0].container_port = port

        apps_v1.patch_namespaced_deployment(name, namespace, deployment)
        logger.info(f"Updated Deployment {name} in {namespace}")

        # Update Service if port has changed
        core_v1 = client.CoreV1Api()
        service = core_v1.read_namespaced_service(name, namespace)
        if port is not None:
            service.spec.ports[0].port = port
            service.spec.ports[0].target_port = port
            core_v1.patch_namespaced_service(name, namespace, service)
            logger.info(f"Updated Service {name} in {namespace}")

        # Update HPA
        autoscaling_v1 = client.AutoscalingV1Api()
        hpa = autoscaling_v1.read_namespaced_horizontal_pod_autoscaler(name, namespace)

        # Update HPA metrics
        metrics = []
        if cpu_threshold:
            metrics.append(client.V2MetricSpec(
                type='Resource',
                resource=client.V2ResourceMetricSource(
                    name='cpu',
                    target=client.V2MetricTarget(
                        type='Utilization',
                        average_utilization=int(cpu_threshold[:-1])
                    )
                )
            ))
        if memory_threshold:
            metrics.append(client.V2MetricSpec(
                type='Resource',
                resource=client.V2ResourceMetricSource(
                    name='memory',
                    target=client.V2MetricTarget(
                        type='Utilization',
                        average_utilization=int(memory_threshold[:-2])
                    )
                )
            ))

        hpa.spec.metrics = metrics
        autoscaling_v1.patch_namespaced_horizontal_pod_autoscaler(name, namespace, hpa)
        logger.info(f"Updated HPA {name} in {namespace}")

    except Exception as e:
        logger.error(f"Error updating application {name} in {namespace}: {e}")


def delete_servicemonitor(name, namespace, logger):
    api = client.CustomObjectsApi()
    try:
        api.delete_namespaced_custom_object(
            group="monitoring.coreos.com",
            version="v1",
            namespace=namespace,
            plural="servicemonitors",
            name=f"{name}-monitor",
            body=client.V1DeleteOptions()
        )
        logger.info(f"Deleted ServiceMonitor {name}-monitor in {namespace}.")
    except Exception as e:
        logger.error(f"Failed to delete ServiceMonitor: {e}")


@kopf.on.delete('mydomain.com', 'v1', 'applications')
def delete_application(name, namespace, **kwargs):
    try:
        apps_v1 = client.AppsV1Api()
        core_v1 = client.CoreV1Api()
        autoscaling_v1 = client.AutoscalingV1Api()

        # Delete HPA
        autoscaling_v1.delete_namespaced_horizontal_pod_autoscaler(name, namespace)
        logger.info(f"Deleted HPA {name} in {namespace}")

        # Delete Deployment
        apps_v1.delete_namespaced_deployment(name=name, namespace=namespace)
        logger.info(f"Deleted Deployment {name} in {namespace}")

        # Delete Service
        core_v1.delete_namespaced_service(name=name, namespace=namespace)
        logger.info(f"Deleted Service {name} in {namespace}")

        delete_servicemonitor(name, namespace, logger)

    except Exception as e:
        logger.error(f"Error deleting application {name} in {namespace}: {e}")
