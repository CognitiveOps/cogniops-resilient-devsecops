FROM openpolicyagent/opa:latest-static
COPY policies/ /policies/
ENTRYPOINT ["./opa"]
CMD ["run", "--server", "--addr=:8181", "--set=decision_logs.console=true", "/policies/"]
