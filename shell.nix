{ pkgs ? import <nixpkgs> { } }:
let
  venv = pkgs.python3.withPackages (
    pythonPackages: with pythonPackages; [
      black
      ipykernel

      kubernetes
    ]
  );
  scripts = pkgs.lib.mapAttrsToList pkgs.writeShellScriptBin {
    mk-pretty = ''
      nixpkgs-fmt .
      black .
      black_nbconvert .
    '';
    mk-ipykernel = "${venv}/bin/ipython kernel install --user --name telegraf-sidecar";
    mk-dockerimg = ''
      eval $(minishift docker-env)
      docker build -t pyenv .
    '';
  };
in
pkgs.mkShell {
  buildInputs = with pkgs; [
    kubernetes-helm
    scripts
    venv
    minishift
    openshift
  ];
}
