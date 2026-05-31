package com.ped3.chat.shared.testsupport;

import jakarta.persistence.EntityManager;
import jakarta.persistence.TypedQuery;

import java.lang.reflect.InvocationHandler;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;
import java.util.List;
import java.util.Map;

public final class JpaTestDoubles {
    private JpaTestDoubles() {
    }

    @SuppressWarnings("unchecked")
    public static <T> TypedQuery<T> typedQuery(List<T> results) {
        return (TypedQuery<T>) Proxy.newProxyInstance(
                TypedQuery.class.getClassLoader(),
                new Class[]{TypedQuery.class},
                new TypedQueryInvocationHandler<>(results));
    }

    public static EntityManager entityManager(Map<Class<?>, TypedQuery<?>> queries) {
        return entityManager(queries, () -> {
        });
    }

    @SuppressWarnings("unchecked")
    public static EntityManager entityManager(Map<Class<?>, TypedQuery<?>> queries, Runnable onPersist) {
        return (EntityManager) Proxy.newProxyInstance(
                EntityManager.class.getClassLoader(),
                new Class[]{EntityManager.class},
                (proxy, method, args) -> handleEntityManagerMethod(method, args, queries, onPersist));
    }

    private static Object handleEntityManagerMethod(Method method, Object[] args, Map<Class<?>, TypedQuery<?>> queries,
                                                    Runnable onPersist) {
        return switch (method.getName()) {
            case "createNativeQuery" -> handleCreateNativeQuery(args, queries);
            case "persist" -> {
                onPersist.run();
                yield null;
            }
            case "flush", "close", "clear", "joinTransaction" -> null;
            default -> defaultValue(method.getReturnType());
        };
    }

    private static Object handleCreateNativeQuery(Object[] args, Map<Class<?>, TypedQuery<?>> queries) {
        if (args != null && args.length == 2 && args[1] instanceof Class<?> entityClass) {
            TypedQuery<?> query = queries.get(entityClass);
            if (query != null) {
                return query;
            }
        }
        throw new IllegalStateException("No test double configured for createNativeQuery call");
    }

    private static Object defaultValue(Class<?> returnType) {
        if (!returnType.isPrimitive()) {
            return null;
        }
        if (returnType == boolean.class) {
            return false;
        }
        if (returnType == byte.class) {
            return (byte) 0;
        }
        if (returnType == short.class) {
            return (short) 0;
        }
        if (returnType == int.class) {
            return 0;
        }
        if (returnType == long.class) {
            return 0L;
        }
        if (returnType == float.class) {
            return 0f;
        }
        if (returnType == double.class) {
            return 0d;
        }
        if (returnType == char.class) {
            return '\0';
        }
        return null;
    }

    private static final class TypedQueryInvocationHandler<T> implements InvocationHandler {
        private final List<T> results;

        private TypedQueryInvocationHandler(List<T> results) {
            this.results = results;
        }

        @Override
        public Object invoke(Object proxy, Method method, Object[] args) {
            return switch (method.getName()) {
                case "setParameter" -> proxy;
                case "getResultList" -> results;
                case "getSingleResult" -> results.isEmpty() ? null : results.get(0);
                default -> defaultValue(method.getReturnType());
            };
        }
    }
}