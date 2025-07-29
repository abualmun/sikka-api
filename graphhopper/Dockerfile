FROM eclipse-temurin:17-jdk

WORKDIR /app

COPY . .

EXPOSE 8989

CMD ["java", "-Xmx8g", "-jar", "web/target/graphhopper-web-11.0-SNAPSHOT.jar", "server", "config.yml"]
