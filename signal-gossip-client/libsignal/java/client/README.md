# Libsignal - Java Client

Contrary to the tech stack of Signal (where the communication via WS/gRPC happens in the Libsignal-net layer), I implement everything into this layer already.

- I added the gRPC classes of libsignal-keytrans and the KT Server into `libsignal/java/client/src/proto`. chat, store and wire belong to `libsignal-keytrans`, and the other 2 to the KT Server.
- I added the needed classes to client/build.gradle
- I compile classes from the given Protobuf definitons.

