#!/usr/bin/env python3

import argparse
import logging
import sys
import time

from kubernetes import client, config
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)


def get_k8s_namespace() -> str:
    """
    tries to fetch kubernetes namespace from pod environment
    :return: returns the namespace if successfully detected, otherwise returns None
    """
    ns_path = Path("/var/run/secrets/kubernetes.io/serviceaccount/namespace")
    if ns_path.is_file():
        return ns_path.open().read()
    return None


def clear_configmap(api: client.CoreV1Api, name: str, namespace: str) -> None:
    """ drops all configmap items """
    cm = api.read_namespaced_config_map(name, namespace)
    if cm.data:
        api.patch_namespaced_config_map(
            name, namespace, {"data": {k: None for k in cm.data}}
        )


def cycle_deployment_replicas(api: client.AppsV1Api, name: str, namespace: str) -> bool:
    scale = api.read_namespaced_deployment_scale(name, namespace).spec.replicas
    if scale == 0:
        logger.error("current scale is 0, aborting replica cycling")
        return False
    logger.info("scaling to 0 replicas...")
    api.patch_namespaced_deployment_scale(name, namespace, {"spec": {"replicas": 0}})
    time.sleep(2)
    logger.info("scaling to %s replicas...", scale)
    api.patch_namespaced_deployment_scale(
        name, namespace, {"spec": {"replicas": scale}}
    )
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--namespace",
        "-ns",
        help="namespace to use, will be read from local pod environment if not specified",
    )
    parser.add_argument("--configmap", "-cm", help="name of configmap to update")
    parser.add_argument(
        "--deployment",
        "-dp",
        help="name of deployment whose pods will be restarted if specified",
    )
    parser.add_argument(
        "--show-config",
        "-s",
        help="only fetch the config and print it, no kubernetes connection will be established",
        action="store_true",
    )
    args = parser.parse_args()

    if args.show_config:
        new_config = fetch_config()
        import pprint

        pprint.pprint(new_config)
        sys.exit(0)
    elif args.configmap is None:
        parser.error("--configmap/-cm must be specified")

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )

    namespace = get_k8s_namespace()
    if namespace is None:
        logger.info("loading local kube config")
        config.load_kube_config()
        namespace = args.namespace
    else:
        logger.info("loading in-cluster kube config")
        config.load_incluster_config()

    if namespace is None:
        logger.error("please specify namespace")
        sys.exit(1)

    logger.info("using namespace: %s" % namespace)

    logger.info("fetching updated config...")
    try:
        new_config = fetch_config()
        logger.info("config fetched successfully, contains %s files" % len(new_config))
    except Exception as e:
        logger.exception("fetching config failed, exiting.")
        sys.exit(1)

    corev1 = client.CoreV1Api()
    appsv1 = client.AppsV1Api()

    logger.info("clearing configmap %s", args.configmap)
    clear_configmap(corev1, args.configmap, namespace)
    logger.info("configmap cleared")

    logger.info("updating configmap %s", args.configmap)
    corev1.patch_namespaced_config_map(args.configmap, namespace, {"data": new_config})
    logger.info("configmap updated")

    if args.deployment:
        logger.info("deployment specified, cycling replicas")
        if not cycle_deployment_replicas(appsv1, args.deployment, namespace):
            sys.exit(1)
        logger.info("cycled replicas successfully")


def fetch_config() -> Dict[str, str]:
    return {"abc.conf": "#foo", "def.conf": "#bar"}


if __name__ == "__main__":
    main()
